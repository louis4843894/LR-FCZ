// Traces only the resource request initializer and its manager entry points.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.mem.Memory;
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.LinkedHashSet;
import java.util.Set;

public class TraceResourceLoad extends GhidraScript {
    private static final String[] ENTRIES = {"01a42ba0", "01a1ff18", "0138dd30"};
    private static final String REQUEST_VTABLE = "01f65118";
    private static final String MANAGER_VTABLE = "01f64680";
    private static final int MAX_FUNCTIONS = 8;
    private static final int MAX_SOURCE_CHARS = 18000;

    private BufferedWriter report;
    private DecompInterface decompiler;
    private final Set<String> written = new LinkedHashSet<>();

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) {
            throw new IllegalArgumentException(
                "Usage: TraceResourceLoad.java <output-report-path>");
        }
        try (BufferedWriter output = Files.newBufferedWriter(
                Paths.get(args[0]), StandardCharsets.UTF_8)) {
            report = output;
            decompiler = new DecompInterface();
            if (!decompiler.openProgram(currentProgram)) {
                throw new IllegalStateException("Could not open saved Ghidra program");
            }
            try {
                writeLine("Program: " + currentProgram.getName());
                writeLine("Analysis mode: saved project only; no auto-analysis");
                for (String entry : ENTRIES) {
                    Address address = currentProgram.getAddressFactory()
                        .getDefaultAddressSpace().getAddress(entry);
                    Function function = currentProgram.getFunctionManager()
                        .getFunctionAt(address);
                    if (function == null) {
                        writeLine("FUNCTION_NOT_DEFINED: " + entry);
                        continue;
                    }
                    writeFunction(function);
                    writeDirectCalls(function);
                }
                dumpVtable("REQUEST", REQUEST_VTABLE, 0x120);
                dumpVtable("MANAGER", MANAGER_VTABLE, 0xb8);
                writeLine("INSPECTED_FUNCTION_COUNT: " + written.size());
                writeLine("REPORT_COMPLETE");
            }
            finally {
                decompiler.dispose();
            }
        }
    }

    private void writeFunction(Function function) throws Exception {
        String entry = function.getEntryPoint().toString();
        if (!written.add(entry)) {
            writeLine("FUNCTION_ALREADY_RECORDED: " + entry);
            return;
        }
        if (written.size() > MAX_FUNCTIONS) {
            written.remove(entry);
            writeLine("FUNCTION_LIMIT_REACHED: " + entry);
            return;
        }
        writeLine("FUNCTION: " + function.getName() + " entry=" + entry);
        DecompileResults result = decompiler.decompileFunction(function, 20, monitor);
        if (result == null || !result.decompileCompleted()
                || result.getDecompiledFunction() == null) {
            writeLine("  DECOMPILE_INCOMPLETE");
            return;
        }
        String source = result.getDecompiledFunction().getC();
        if (source != null) {
            writeLine(source.substring(0, Math.min(source.length(), MAX_SOURCE_CHARS)));
        }
        writeLine("");
    }

    private void writeDirectCalls(Function function) throws Exception {
        writeLine("DIRECT_CALLS_FROM: " + function.getEntryPoint());
        int count = 0;
        for (Instruction instruction :
                currentProgram.getListing().getInstructions(function.getBody(), true)) {
            for (Reference reference :
                    currentProgram.getReferenceManager().getReferencesFrom(
                        instruction.getAddress())) {
                if (!reference.getReferenceType().isCall()) {
                    continue;
                }
                Function called = currentProgram.getFunctionManager()
                    .getFunctionAt(reference.getToAddress());
                writeLine("  CALL: " + instruction.getAddress() + " -> "
                    + reference.getToAddress() + " "
                    + (called == null ? "<no function>" : called.getName()));
                if (++count >= 40) {
                    writeLine("  DIRECT_CALL_LIMIT_REACHED");
                    return;
                }
            }
        }
        writeLine("  DIRECT_CALL_COUNT: " + count);
    }

    private Function dumpVtable(String label, String vtableAddress, int maxOffset)
            throws Exception {
        Address vtable = currentProgram.getAddressFactory()
            .getDefaultAddressSpace().getAddress(vtableAddress);
        Memory memory = currentProgram.getMemory();
        Function requestMethod = null;
        writeLine(label + "_VTABLE_BASE: " + vtable);
        for (int offset = 0; offset <= maxOffset; offset += Long.BYTES) {
            Address slot = vtable.add(offset);
            Address targetAddress = currentProgram.getAddressFactory()
                .getDefaultAddressSpace().getAddress(memory.getLong(slot));
            Function target = currentProgram.getFunctionManager()
                .getFunctionAt(targetAddress);
            Symbol symbol = currentProgram.getSymbolTable()
                .getPrimarySymbol(targetAddress);
            writeLine("  " + label + "_VTABLE_SLOT: +" + Integer.toHexString(offset)
                + " " + slot + " -> " + targetAddress
                + " function=" + (target == null ? "<no function>" : target.getName())
                + " symbol=" + (symbol == null ? "<none>" : symbol.getName()));
            if (label.equals("MANAGER")
                    && (offset == 0x38 || offset == 0x48 || offset == 0x50
                        || offset == 0x60 || offset == 0xb8)
                    && target != null) {
                if (offset == 0x48) {
                    requestMethod = target;
                }
                writeFunction(target);
                writeDirectCalls(target);
            }
        }
        return requestMethod;
    }

    private void writeLine(String value) throws Exception {
        report.write(value);
        report.newLine();
    }
}
