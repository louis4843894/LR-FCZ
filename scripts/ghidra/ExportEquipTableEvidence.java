// Exports the existing equipment descriptor and only its direct references.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;

public class ExportEquipTableEvidence extends GhidraScript {
    private static final String DESCRIPTOR_ENTRY = "00f44fb8";
    private static final String DESCRIPTOR_DATA = "01e4aaa0";
    private static final String DESCRIPTOR_HEADING =
        "    FUNCTION: FUN_00f44fb8 entry=00f44fb8";
    private static final int MAX_CALLER_FUNCTIONS = 3;

    private BufferedWriter output;
    private DecompInterface decompiler;
    private int callerFunctionCount;

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) {
            throw new IllegalArgumentException(
                "Usage: ExportEquipTableEvidence.java <output-path> <existing-xref-report>");
        }

        Path sourceReport = Paths.get(args[1]);
        if (!Files.isRegularFile(sourceReport)) {
            throw new IllegalStateException(
                "Existing xref report is missing: " + sourceReport);
        }
        try (BufferedWriter writer = Files.newBufferedWriter(
                Paths.get(args[0]), StandardCharsets.UTF_8)) {
            output = writer;
            decompiler = new DecompInterface();
            if (!decompiler.openProgram(currentProgram)) {
                throw new IllegalStateException("Could not open saved Ghidra program");
            }
            try {
                writeLine("Source project: " + currentProgram.getName());
                writeLine("Analysis: saved project only; auto-analysis disabled");
                writeLine("Existing xref report: " + sourceReport);
                writeLine("");
                writeExistingDescriptor(sourceReport);
                writeDirectReferences();
                writeDescriptorPointerContext();
                writeLine("INSPECTED_CALLER_FUNCTIONS: " + callerFunctionCount);
                writeLine("REPORT_COMPLETE");
            }
            finally {
                decompiler.dispose();
            }
        }
    }

    private void writeExistingDescriptor(Path sourceReport) throws Exception {
        List<String> lines = Files.readAllLines(sourceReport, StandardCharsets.UTF_8);
        int start = -1;
        for (int i = 0; i < lines.size(); i++) {
            if (lines.get(i).equals(DESCRIPTOR_HEADING)) {
                start = i;
                break;
            }
        }
        if (start < 0) {
            throw new IllegalStateException(
                "Existing FUN_00f44fb8 code was not found in " + sourceReport);
        }
        int end = start + 1;
        while (end < lines.size()
                && !lines.get(end).startsWith("      CALLER_REFERENCE_COUNT:")) {
            end++;
        }
        if (end == lines.size()) {
            throw new IllegalStateException(
                "Existing descriptor reference section was not found in " + sourceReport);
        }
        writeLine("=== EXISTING DESCRIPTOR FUNCTION: FUN_00f44fb8 ===");
        for (int i = start; i < end; i++) {
            writeLine(lines.get(i));
        }
        writeLine("=== END EXISTING DESCRIPTOR FUNCTION ===");
        writeLine("");
    }

    private void writeDirectReferences() throws Exception {
        Address functionAddress = address(DESCRIPTOR_ENTRY);
        Address dataAddress = address(DESCRIPTOR_DATA);
        writeLine("=== DIRECT REFERENCES ===");
        writeReferencesTo("DESCRIPTOR_FUNCTION", functionAddress);
        writeReferencesTo("DESCRIPTOR_DATA", dataAddress);
        writeLine("=== END DIRECT REFERENCES ===");
        writeLine("");
    }

    private void writeReferencesTo(String label, Address target) throws Exception {
        writeLine(label + "_ADDRESS: " + target);
        ReferenceIterator references =
            currentProgram.getReferenceManager().getReferencesTo(target);
        int count = 0;
        while (references.hasNext()) {
            Reference reference = references.next();
            Function caller = currentProgram.getFunctionManager()
                .getFunctionContaining(reference.getFromAddress());
            writeLine("REFERENCE: from=" + reference.getFromAddress()
                + " type=" + reference.getReferenceType()
                + " source=" + reference.getSource()
                + " caller=" + (caller == null ? "<no function>" : caller.getName()));
            if (caller != null && !caller.getEntryPoint().equals(functionAddress())
                    && callerFunctionCount < MAX_CALLER_FUNCTIONS) {
                writeCaller(caller);
            }
            count++;
        }
        writeLine(label + "_REFERENCE_COUNT: " + count);
    }

    private void writeCaller(Function function) throws Exception {
        if (function.getName().equals("FUN_00f44fb8")) {
            return;
        }
        callerFunctionCount++;
        writeLine("=== DIRECT REFERENCING FUNCTION: " + function.getName()
            + " entry=" + function.getEntryPoint() + " ===");
        DecompileResults result = decompiler.decompileFunction(function, 60, monitor);
        if (result == null || !result.decompileCompleted()
                || result.getDecompiledFunction() == null) {
            writeLine("DECOMPILATION_INCOMPLETE");
        }
        else {
            writeLine(result.getDecompiledFunction().getC());
        }
        writeLine("=== END DIRECT REFERENCING FUNCTION ===");
        writeLine("");
    }

    private void writeDescriptorPointerContext() throws Exception {
        Address base = address(DESCRIPTOR_DATA);
        Memory memory = currentProgram.getMemory();
        writeLine("=== NEARBY POINTER DATA (RAW, NOT ASSUMED TO BE A REGISTRY) ===");
        for (int offset = -0x20; offset <= 0x20; offset += Long.BYTES) {
            Address slot = base.add(offset);
            long value = memory.getLong(slot);
            Address target = currentProgram.getAddressFactory()
                .getDefaultAddressSpace().getAddress(value);
            Function function = currentProgram.getFunctionManager().getFunctionAt(target);
            writeLine("DATA_SLOT: " + slot + " value=" + target
                + " function=" + (function == null ? "<no function>" : function.getName()));
        }
        writeLine("=== END NEARBY POINTER DATA ===");
        writeLine("");
    }

    private Address address(String value) throws Exception {
        return currentProgram.getAddressFactory()
            .getDefaultAddressSpace().getAddress(value);
    }

    private Address functionAddress() throws Exception {
        return address(DESCRIPTOR_ENTRY);
    }

    private void writeLine(String value) throws Exception {
        output.write(value);
        output.newLine();
    }
}
