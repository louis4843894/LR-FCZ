// Inspects the saved CCFileUtils call path without running program analysis.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class InspectFileUtilsDispatch extends GhidraScript {
    private static final String TARGET_ENTRY = "01a408fc";
    private static final String SHARED_IMPLEMENTATION_POINTER = "01fbcfd8";
    private static final Pattern CONSTRUCTOR_THUNK_POINTER =
        Pattern.compile("PTR_CCFileUtilsAndroid_([0-9a-fA-F]{8,16})");
    private static final Pattern ADRP_X8 =
        Pattern.compile("adrp x8,\\s*0x([0-9a-fA-F]+)");
    private static final Pattern LDR_X8 =
        Pattern.compile("ldr x8,\\[x8,\\s*#0x([0-9a-fA-F]+)\\]");
    private static final int MAX_FUNCTIONS = 5;
    private static final int MAX_SOURCE_CHARS = 24000;

    private BufferedWriter report;
    private DecompInterface decompiler;
    private final Set<String> writtenFunctions = new LinkedHashSet<>();

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) {
            throw new IllegalArgumentException(
                "Usage: InspectFileUtilsDispatch.java <output-report-path>");
        }

        Path output = Paths.get(args[0]);
        try (BufferedWriter writer = Files.newBufferedWriter(
                output, StandardCharsets.UTF_8)) {
            report = writer;
            decompiler = new DecompInterface();
            if (!decompiler.openProgram(currentProgram)) {
                throw new IllegalStateException("Could not open the saved Ghidra program");
            }
            try {
                writeLine("Program: " + currentProgram.getName());
                writeLine("Analysis mode: saved project only; no auto-analysis");

                Address targetAddress = currentProgram.getAddressFactory()
                    .getDefaultAddressSpace().getAddress(TARGET_ENTRY);
                Function target = currentProgram.getFunctionManager()
                    .getFunctionAt(targetAddress);
                if (target == null) {
                    throw new IllegalStateException(
                        "Target function not found at " + TARGET_ENTRY);
                }

                writeFunction(target, "TARGET_FUNCTION");
                Function shared = findSharedFileUtils(target);
                if (shared == null) {
                    writeLine("SHARED_FILE_UTILS_FUNCTION_NOT_FOUND");
                }
                else {
                    writeLine("SHARED_FILE_UTILS_WRAPPER: "
                        + shared.getEntryPoint() + " " + shared.getName());
                    writeSharedImplementation();
                }
                writeLine("INSPECTED_FUNCTION_COUNT: " + writtenFunctions.size());
                writeLine("REPORT_COMPLETE");
            }
            finally {
                decompiler.dispose();
            }
        }
    }

    private Function findSharedFileUtils(Function target) throws Exception {
        for (Instruction instruction :
                currentProgram.getListing().getInstructions(target.getBody(), true)) {
            Reference[] references = currentProgram.getReferenceManager()
                .getReferencesFrom(instruction.getAddress());
            for (Reference reference : references) {
                if (!reference.getReferenceType().isCall()) {
                    continue;
                }
                Function called = currentProgram.getFunctionManager()
                    .getFunctionAt(reference.getToAddress());
                if (called != null && called.getName().contains("sharedFileUtils")) {
                    writeLine("SHARED_FILE_UTILS_CALL: " + instruction.getAddress()
                        + " -> " + called.getEntryPoint()
                        + " " + called.getName());
                    return called;
                }
            }
        }
        return null;
    }

    private void writeSharedImplementation() throws Exception {
        Address pointerAddress = currentProgram.getAddressFactory()
            .getDefaultAddressSpace().getAddress(SHARED_IMPLEMENTATION_POINTER);
        Address implementation = currentProgram.getAddressFactory()
            .getDefaultAddressSpace().getAddress(
                currentProgram.getMemory().getLong(pointerAddress));
        Function function = currentProgram.getFunctionManager()
            .getFunctionAt(implementation);
        writeLine("SHARED_IMPLEMENTATION_POINTER: "
            + pointerAddress + " -> " + implementation);
        if (function == null) {
            writeLine("SHARED_IMPLEMENTATION_FUNCTION_NOT_DEFINED");
            return;
        }
        writeFunction(function, "SHARED_IMPLEMENTATION_FUNCTION");
        Function constructorThunk =
            findDirectCallContaining(function, "CCFileUtilsAndroid");
        if (constructorThunk == null) {
            writeLine("CCFILEUTILS_ANDROID_CONSTRUCTOR_NOT_FOUND");
            return;
        }
        String constructorSource =
            writeFunction(constructorThunk, "CCFILEUTILS_ANDROID_CONSTRUCTOR_THUNK");
        inspectConstructorTarget(constructorSource);
    }

    private Function findDirectCallContaining(Function caller, String nameFragment)
            throws Exception {
        for (Instruction instruction :
                currentProgram.getListing().getInstructions(caller.getBody(), true)) {
            Reference[] references = currentProgram.getReferenceManager()
                .getReferencesFrom(instruction.getAddress());
            for (Reference reference : references) {
                if (!reference.getReferenceType().isCall()) {
                    continue;
                }
                Function called = currentProgram.getFunctionManager()
                    .getFunctionAt(reference.getToAddress());
                if (called != null && called.getName().contains(nameFragment)) {
                    writeLine("CONSTRUCTOR_CALL: " + instruction.getAddress()
                        + " -> " + called.getEntryPoint() + " " + called.getName());
                    return called;
                }
            }
        }
        return null;
    }

    private void inspectConstructorTarget(String constructorSource) throws Exception {
        if (constructorSource == null) {
            writeLine("CONSTRUCTOR_THUNK_NOT_DECOMPILED");
            return;
        }
        Matcher thunkPointerMatcher =
            CONSTRUCTOR_THUNK_POINTER.matcher(constructorSource);
        if (!thunkPointerMatcher.find()) {
            writeLine("CONSTRUCTOR_THUNK_TARGET_NOT_RESOLVED");
            return;
        }
        Address thunkPointerSlot = currentProgram.getAddressFactory()
            .getDefaultAddressSpace().getAddress(thunkPointerMatcher.group(1));
        Address constructorAddress = currentProgram.getAddressFactory()
            .getDefaultAddressSpace().getAddress(
                currentProgram.getMemory().getLong(thunkPointerSlot));
        writeLine("CONSTRUCTOR_THUNK_POINTER_SLOT: " + thunkPointerSlot
            + " -> " + constructorAddress);

        Long pageBase = null;
        Long pageOffset = null;
        boolean storesAdjustedVtable = false;
        Instruction instruction = currentProgram.getListing()
            .getInstructionAt(constructorAddress);
        for (int count = 0; instruction != null && count < 16; count++) {
            String text = instruction.toString();
            writeLine("  CONSTRUCTOR_INITIALIZATION: "
                + instruction.getAddress() + " " + text);
            Matcher adrp = ADRP_X8.matcher(text);
            Matcher ldr = LDR_X8.matcher(text);
            if (adrp.find()) {
                pageBase = Long.parseUnsignedLong(adrp.group(1), 16);
            }
            if (ldr.find()) {
                pageOffset = Long.parseUnsignedLong(ldr.group(1), 16);
            }
            if (text.startsWith("add x8,x8,#0x10")
                    || text.startsWith("add x8,x8, #0x10")) {
                storesAdjustedVtable = true;
            }
            if (pageBase != null && pageOffset != null && storesAdjustedVtable
                    && text.startsWith("str x8")) {
                break;
            }
            if ("RET".equalsIgnoreCase(instruction.getMnemonicString())) {
                break;
            }
            instruction = currentProgram.getListing().getInstructionAfter(
                instruction.getAddress());
        }
        if (pageBase == null || pageOffset == null || !storesAdjustedVtable) {
            writeLine("VTABLE_INITIALIZATION_NOT_CONFIRMED_FROM_INSTRUCTIONS");
            return;
        }
        Address pointerSlot = currentProgram.getAddressFactory()
            .getDefaultAddressSpace().getAddress(pageBase).add(pageOffset);
        Address vtableBase = currentProgram.getAddressFactory()
            .getDefaultAddressSpace()
            .getAddress(currentProgram.getMemory().getLong(pointerSlot));
        Address addressPoint = vtableBase.add(0x10);
        Address slot = addressPoint.add(0x80);
        Address targetAddress = currentProgram.getAddressFactory()
            .getDefaultAddressSpace()
            .getAddress(currentProgram.getMemory().getLong(slot));
        Function target = currentProgram.getFunctionManager().getFunctionAt(targetAddress);
        writeLine("CONSTRUCTOR_VPTR_INITIALIZATION_CONFIRMED: "
            + "loaded vtable pointer then added 0x10 before storing on this");
        writeLine("CCFILEUTILS_ANDROID_VTABLE_POINTER_SLOT: " + pointerSlot);
        writeLine("CCFILEUTILS_ANDROID_VTABLE_BASE: " + vtableBase);
        writeLine("CCFILEUTILS_ANDROID_VTABLE_ADDRESS_POINT: "
            + addressPoint + " (constructor adds 0x10 before storing this)");
        writeLine("CCFILEUTILS_ANDROID_VTABLE_PLUS_0x80: " + slot + " -> "
            + targetAddress + " function="
            + (target == null ? "<no function>" : target.getName()));
        if (target != null) {
            writeFunction(target, "VIRTUAL_SLOT_FUNCTION");
        }
    }

    private String writeFunction(Function function, String label) throws Exception {
        String entry = function.getEntryPoint().toString();
        if (writtenFunctions.contains(entry)) {
            writeLine(label + ": " + function.getName()
                + " entry=" + entry + " (already recorded)");
            return null;
        }
        if (writtenFunctions.size() >= MAX_FUNCTIONS) {
            writeLine(label + ": FUNCTION_LIMIT_REACHED at " + entry);
            return null;
        }
        writtenFunctions.add(entry);
        writeLine(label + ": " + function.getName() + " entry=" + entry);
        DecompileResults result = decompiler.decompileFunction(function, 20, monitor);
        if (result == null || !result.decompileCompleted()
                || result.getDecompiledFunction() == null) {
            writeLine("  DECOMPILE_INCOMPLETE");
            return null;
        }
        String source = result.getDecompiledFunction().getC();
        if (source == null) {
            writeLine("  DECOMPILE_EMPTY");
            return null;
        }
        writeLine(source.substring(0, Math.min(source.length(), MAX_SOURCE_CHARS)));
        writeLine("");
        return source;
    }

    private void writeLine(String value) throws Exception {
        report.write(value);
        report.newLine();
    }
}
