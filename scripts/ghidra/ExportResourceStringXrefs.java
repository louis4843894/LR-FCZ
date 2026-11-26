// Searches the saved program and records references, containing functions, and callers for resource strings.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.ReferenceManager;
import ghidra.util.task.TaskMonitor;
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class ExportResourceStringXrefs extends GhidraScript {
    private static final String[] NEEDLES = {
        "game_item_equip",
        "resourcePath",
        "resourceId",
        "res_base_hd.txt",
        "eqip_spcl_opt"
    };
    private static final String[] FOCUSED_FUNCTIONS = {
        "01a41444",
        "01a26ef0",
        "01a408fc",
        "01a42d18",
        "01a4e4c8",
        "01a42720",
        "01a42754",
        "01a42788",
        "01a427bc",
        "01a427cc",
        "01a427d4",
        "01a42884",
        "01a4289c"
    };
    private static final String[] FOCUSED_POINTER_TABLES = {
        "01f65008"
    };
    private static final String[] FOCUSED_DATA = {
        "01e4aaa0",
        "01e4afa0"
    };
    private static final int MAX_DECOMPILED_FUNCTIONS = 48;
    private static final int MAX_REFERENCES_PER_ADDRESS = 100;
    private static final int MAX_CALLERS_PER_FUNCTION = 40;
    private static final int MAX_DECOMPILED_CHARS = 65536;

    private BufferedWriter writer;
    private DecompInterface decompiler;
    private final Set<String> decompiledEntries = new LinkedHashSet<>();

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) {
            throw new IllegalArgumentException(
                "Usage: ExportResourceStringXrefs.java <output-report-path>");
        }

        Path output = Paths.get(args[0]);
        try (BufferedWriter report = Files.newBufferedWriter(
                output, StandardCharsets.UTF_8)) {
            writer = report;
            decompiler = new DecompInterface();
            decompiler.openProgram(currentProgram);
            try {
                writeLine("Program: " + currentProgram.getName());
                writeLine("Language: " + currentProgram.getLanguageID());
                writeLine("Image base: " + currentProgram.getImageBase());
                writeLine("");

                Memory memory = currentProgram.getMemory();
                Address minimum = memory.getMinAddress();
                Address maximum = memory.getMaxAddress();
                ReferenceManager references = currentProgram.getReferenceManager();

                for (String needle : NEEDLES) {
                    searchNeedle(memory, references, minimum, maximum, needle);
                }
                for (String functionAddress : FOCUSED_FUNCTIONS) {
                    Address address = currentProgram.getAddressFactory()
                        .getDefaultAddressSpace().getAddress(functionAddress);
                    Function function = currentProgram.getFunctionManager()
                        .getFunctionAt(address);
                    writeLine("FOCUSED_FUNCTION: " + functionAddress);
                    if (function == null) {
                        writeLine("  FUNCTION_NOT_DEFINED");
                    }
                    else {
                        writeFunction(function, "  FUNCTION");
                    }
                    writeLine("");
                }
                for (String dataAddress : FOCUSED_DATA) {
                    Address address = currentProgram.getAddressFactory()
                        .getDefaultAddressSpace().getAddress(dataAddress);
                    Data data = currentProgram.getListing()
                        .getDefinedDataContaining(address);
                    writeLine("FOCUSED_DATA: " + dataAddress);
                    if (data == null) {
                        writeLine("  DATA_NOT_DEFINED");
                    }
                    else {
                        writeLine("  DATA: " + data.getAddress()
                            + " type=" + data.getDataType().getName()
                            + " length=" + data.getLength()
                            + " value=" + data.getValue());
                    }
                    writeLine("");
                }
                for (String tableAddress : FOCUSED_POINTER_TABLES) {
                    writePointerTable(memory, tableAddress, 0xd0);
                }
                writeLine("DECOMPILED_FUNCTION_COUNT: " + decompiledEntries.size());
                writeLine("REPORT_COMPLETE");
            }
            finally {
                decompiler.dispose();
            }
        }
    }

    private void searchNeedle(
            Memory memory,
            ReferenceManager referenceManager,
            Address minimum,
            Address maximum,
            String needle) throws Exception {
        writeLine("STRING: " + needle);
        byte[] bytes = needle.getBytes(StandardCharsets.US_ASCII);
        Address cursor = minimum;
        int occurrences = 0;
        while (cursor != null && cursor.compareTo(maximum) <= 0) {
            Address address = memory.findBytes(
                cursor, maximum, bytes, null, true, monitor);
            if (address == null) {
                break;
            }
            occurrences++;
            writeLine("  ADDRESS: " + address);

            Map<String, Reference> references = referencesAt(
                referenceManager, address);
            Data containingData = currentProgram.getListing()
                .getDefinedDataContaining(address);
            if (containingData != null
                    && !containingData.getAddress().equals(address)) {
                writeLine("  CONTAINING_DATA: " + containingData.getAddress()
                    + " type=" + containingData.getDataType().getName());
                addReferences(references, referenceManager, containingData.getAddress());
            }

            writeLine("  REFERENCE_COUNT: " + references.size());
            int written = 0;
            for (Reference reference : references.values()) {
                if (written++ >= MAX_REFERENCES_PER_ADDRESS) {
                    writeLine("  REFERENCE_LIMIT_REACHED");
                    break;
                }
                Address source = reference.getFromAddress();
                Function function = currentProgram.getFunctionManager()
                    .getFunctionContaining(source);
                writeLine("    REF: " + source
                    + " type=" + reference.getReferenceType()
                    + " function=" + (function == null
                        ? "<no function>" : function.getName())
                    + " entry=" + (function == null
                        ? "<none>" : function.getEntryPoint()));
                if (function != null) {
                    writeFunction(function, "    FUNCTION");
                    writeCallers(referenceManager, function);
                }
            }
            cursor = address.add(1);
        }
        writeLine("  OCCURRENCE_COUNT: " + occurrences);
        writeLine("");
    }

    private Map<String, Reference> referencesAt(
            ReferenceManager referenceManager, Address address) {
        Map<String, Reference> found = new LinkedHashMap<>();
        addReferences(found, referenceManager, address);
        return found;
    }

    private void addReferences(
            Map<String, Reference> found,
            ReferenceManager referenceManager,
            Address address) {
        ReferenceIterator iterator = referenceManager.getReferencesTo(address);
        while (iterator.hasNext()) {
            Reference reference = iterator.next();
            String key = reference.getFromAddress().toString()
                + "|" + reference.getReferenceType();
            found.put(key, reference);
        }
    }

    private void writeCallers(
            ReferenceManager referenceManager, Function function) throws Exception {
        List<Reference> callers = new ArrayList<>();
        ReferenceIterator iterator = referenceManager.getReferencesTo(
            function.getEntryPoint());
        while (iterator.hasNext()) {
            callers.add(iterator.next());
        }
        writeLine("      CALLER_REFERENCE_COUNT: " + callers.size());
        int written = 0;
        for (Reference reference : callers) {
            if (written++ >= MAX_CALLERS_PER_FUNCTION) {
                writeLine("      CALLER_LIMIT_REACHED");
                break;
            }
            Address source = reference.getFromAddress();
            Function caller = currentProgram.getFunctionManager()
                .getFunctionContaining(source);
            writeLine("        CALLER: " + source
                + " refType=" + reference.getReferenceType()
                + " function=" + (caller == null
                    ? "<no function>" : caller.getName())
                + " entry=" + (caller == null
                    ? "<none>" : caller.getEntryPoint()));
            Data sourceData = currentProgram.getListing()
                .getDefinedDataContaining(source);
            if (sourceData != null) {
                writeLine("          SOURCE_DATA: " + sourceData.getAddress()
                    + " type=" + sourceData.getDataType().getName()
                    + " length=" + sourceData.getLength());
            }
            else {
                ghidra.program.model.listing.CodeUnit sourceUnit =
                    currentProgram.getListing().getCodeUnitContaining(source);
                if (sourceUnit != null) {
                    writeLine("          SOURCE_CODE_UNIT: "
                        + sourceUnit.getClass().getSimpleName()
                        + " " + sourceUnit.toString());
                }
            }
            if (caller != null) {
                writeFunction(caller, "        CALLER_FUNCTION");
            }
        }
    }

    private void writeFunction(Function function, String label) throws Exception {
        String entry = function.getEntryPoint().toString();
        writeLine(label + ": " + function.getName() + " entry=" + entry);
        if (decompiledEntries.contains(entry)) {
            writeLine("      DECOMPILE_ALREADY_RECORDED");
            return;
        }
        if (decompiledEntries.size() >= MAX_DECOMPILED_FUNCTIONS) {
            writeLine("      DECOMPILE_LIMIT_REACHED");
            return;
        }
        decompiledEntries.add(entry);

        DecompileResults result = decompiler.decompileFunction(function, 45, monitor);
        if (result == null || !result.decompileCompleted()) {
            writeLine("      DECOMPILE_INCOMPLETE");
            return;
        }
        if (result.getDecompiledFunction() == null) {
            writeLine("      DECOMPILE_EMPTY");
            return;
        }
        String source = result.getDecompiledFunction().getC();
        if (source != null) {
            writeLine(source.substring(0, Math.min(source.length(), MAX_DECOMPILED_CHARS)));
        }
    }

    private void writeLine(String value) throws Exception {
        writer.write(value);
        writer.newLine();
    }

    private void writePointerTable(
            Memory memory, String tableAddress, int lastOffset) throws Exception {
        Address base = currentProgram.getAddressFactory()
            .getDefaultAddressSpace().getAddress(tableAddress);
        writeLine("POINTER_TABLE: " + tableAddress);
        for (int offset = 0; offset <= lastOffset; offset += Long.BYTES) {
            Address slot = base.add(offset);
            long pointer = memory.getLong(slot);
            Address target = currentProgram.getAddressFactory()
                .getDefaultAddressSpace().getAddress(pointer);
            Function function = currentProgram.getFunctionManager()
                .getFunctionAt(target);
            writeLine("  SLOT: " + slot + " offset=0x"
                + Integer.toHexString(offset) + " target=" + target
                + " function=" + (function == null
                    ? "<no function>" : function.getName()));
        }
        writeLine("");
    }
}
