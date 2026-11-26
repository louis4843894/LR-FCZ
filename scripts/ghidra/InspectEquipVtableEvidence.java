// Verifies the equipment address point; reuses prior neighbor evidence.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.Symbol;
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public class InspectEquipVtableEvidence extends GhidraScript {
    private static final String DESCRIPTOR_ENTRY = "00f44fb8";
    private static final String DESCRIPTOR_DATA = "01e4aaa0";
    private static final String EXISTING_FUNCTION_HEADING =
        "    FUNCTION: FUN_00f44fb8 entry=00f44fb8";
    private static final String[] REQUIRED_NEIGHBORS = {"00f10bd0", "00f10ed4"};
    private static final int MAX_DECOMPILED_FUNCTIONS = 4;
    private static final int MAX_REFERENCE_CANDIDATES = 2;

    private BufferedWriter output;
    private DecompInterface decompiler;
    private final Set<String> decompiledEntries = new LinkedHashSet<>();

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) {
            throw new IllegalArgumentException(
                "Usage: InspectEquipVtableEvidence.java <output-path> <existing-xref-report>");
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
                inspectPointerRegion();
                inspectReferences();
                writeReferencesTo(address("00f0e074"), "FACTORY_CALLER");
                ReferenceIterator factoryRefs = currentProgram.getReferenceManager().getReferencesTo(address("00f0e074"));
                while (factoryRefs.hasNext()) {
                    Reference ref = factoryRefs.next();
                    Function caller = currentProgram.getFunctionManager().getFunctionContaining(ref.getFromAddress());
                    if (caller != null) { decompileAt(caller.getEntryPoint().toString(), "FACTORY CALLER"); break; }
                }
                for (String entry : REQUIRED_NEIGHBORS) {
                    decompileAt(entry, "ADJACENT VTABLE FUNCTION");
                }
                writeLine("REUSED_NEIGHBOR_EVIDENCE: equip-table-evidence.txt FUN_00f44fe0 / FUN_00f3fef8");
                writeLine("DECOMPILED_FUNCTION_COUNT: " + decompiledEntries.size());
                writeLine("REPORT_COMPLETE");
            }
            finally {
                decompiler.dispose();
            }
        }
    }

    private void writeExistingDescriptor(Path sourceReport) throws Exception {
        List<String> lines = Files.readAllLines(sourceReport, StandardCharsets.UTF_8);
        int start = lines.indexOf(EXISTING_FUNCTION_HEADING);
        if (start < 0) {
            throw new IllegalStateException(
                "Existing FUN_00f44fb8 output was not found in " + sourceReport);
        }
        int end = start + 1;
        while (end < lines.size()
                && !lines.get(end).startsWith("      CALLER_REFERENCE_COUNT:")) {
            end++;
        }
        if (end == lines.size()) {
            throw new IllegalStateException(
                "Existing descriptor references were not found in " + sourceReport);
        }
        writeLine("=== EXISTING FUN_00f44fb8 ===");
        for (int i = start; i < end; i++) {
            writeLine(lines.get(i));
        }
        writeLine("=== END EXISTING FUNCTION ===");
        writeLine("");
    }

    private void inspectPointerRegion() throws Exception {
        Address start = address("01e4aa40");
        Address candidate = address("01e4aa78");
        Address end = address("01e4aae0");
        Memory memory = currentProgram.getMemory();
        writeLine("=== RAW POINTERS AROUND CANDIDATE VTABLE ===");
        writeLine("Candidate descriptor slot: " + address(DESCRIPTOR_DATA));
        writeLine("Candidate address point to verify: " + candidate);
        for (Address slot = start; slot.compareTo(end) <= 0; slot = slot.add(8)) {
            long value = memory.getLong(slot);
            Address target = currentProgram.getAddressFactory()
                .getDefaultAddressSpace().getAddress(value);
            Function function = currentProgram.getFunctionManager().getFunctionAt(target);
            Symbol symbol = currentProgram.getSymbolTable().getPrimarySymbol(target);
            Data data = currentProgram.getListing().getDataAt(target);
            writeLine("POINTER_SLOT: " + slot + " raw=0x"
                + Long.toUnsignedString(value, 16) + " target=" + target
                + " function=" + (function == null ? "<none>" : function.getName())
                + " symbol=" + (symbol == null ? "<none>" : symbol.getName())
                + " data=" + (data == null ? "<none>" : data.getDataType().getName()));
        }
        writeLine("=== END RAW POINTER REGION ===");
        writeLine("");
    }

    private void inspectReferences() throws Exception {
        Address candidate = address("01e4aa78");
        Address typeInfoSlot = candidate.subtract(8);
        Address offsetToTopSlot = candidate.subtract(16);
        writeLine("=== ADDRESS-POINT / RTTI REFERENCES ===");
        writeLine("ADDRESS_POINT_CANDIDATE: " + candidate);
        writeLine("RTTI_SLOT_CANDIDATE: " + typeInfoSlot);
        writeLine("OFFSET_TO_TOP_SLOT_CANDIDATE: " + offsetToTopSlot);
        int references = writeReferencesTo(candidate, "ADDRESS_POINT");
        writeReferencesTo(typeInfoSlot, "RTTI_SLOT");
        writeReferencesTo(offsetToTopSlot, "OFFSET_TO_TOP_SLOT");
        if (references == 0) {
            writeLine("STATIC_ADDRESS_POINT_XREF: none");
            writeLine("ARM64_ADDRESS_COMPOSITION: not inspected; no evidence-based "
                + "constructor/reference location is available.");
        }
        writeLine("=== END ADDRESS-POINT / RTTI REFERENCES ===");
        writeLine("");
    }

    private int writeReferencesTo(Address target, String label) throws Exception {
        writeLine(label + "_TARGET: " + target);
        ReferenceIterator iterator =
            currentProgram.getReferenceManager().getReferencesTo(target);
        int count = 0;
        int inspectedCandidates = 0;
        while (iterator.hasNext()) {
            Reference reference = iterator.next();
            Function function = currentProgram.getFunctionManager()
                .getFunctionContaining(reference.getFromAddress());
            writeLine("REFERENCE: from=" + reference.getFromAddress()
                + " type=" + reference.getReferenceType()
                + " source=" + reference.getSource()
                + " function=" + (function == null ? "<no function>" : function.getName()));
            if (label.equals("ADDRESS_POINT") && function != null
                    && inspectedCandidates < MAX_REFERENCE_CANDIDATES) {
                writeInstructionContext(function, reference.getFromAddress());
                decompileAt(function.getEntryPoint().toString(),
                    "ADDRESS-POINT REFERENCING FUNCTION");
                inspectedCandidates++;
            }
            count++;
        }
        writeLine(label + "_REFERENCE_COUNT: " + count);
        return count;
    }

    private void writeInstructionContext(Function function, Address referenceAddress)
            throws Exception {
        Instruction atReference = currentProgram.getListing().getInstructionAt(referenceAddress);
        if (atReference == null) {
            return;
        }
        writeLine("ADDRESS-POINT INSTRUCTION CONTEXT: " + function.getName());
        Instruction previous = currentProgram.getListing().getInstructionBefore(referenceAddress);
        if (previous != null && function.getBody().contains(previous.getAddress())) {
            writeLine("  " + previous.getAddress() + " " + previous);
        }
        writeLine("  " + atReference.getAddress() + " " + atReference);
        Instruction next = currentProgram.getListing().getInstructionAfter(referenceAddress);
        if (next != null && function.getBody().contains(next.getAddress())) {
            writeLine("  " + next.getAddress() + " " + next);
        }
    }

    private void decompileAt(String entry, String label) throws Exception {
        Address address = address(entry);
        Function function = currentProgram.getFunctionManager().getFunctionAt(address);
        if (function == null) {
            writeLine(label + "_NOT_DEFINED: " + entry);
            return;
        }
        String key = function.getEntryPoint().toString();
        if (decompiledEntries.contains(key)) {
            writeLine("FUNCTION_ALREADY_EXPORTED: " + function.getName()
                + " entry=" + key);
            return;
        }
        if (decompiledEntries.size() >= MAX_DECOMPILED_FUNCTIONS) {
            writeLine("FUNCTION_LIMIT_REACHED: " + function.getName()
                + " entry=" + key);
            return;
        }
        decompiledEntries.add(key);
        writeLine("=== " + label + ": " + function.getName()
            + " entry=" + key + " ===");
        DecompileResults result = decompiler.decompileFunction(function, 60, monitor);
        if (result == null || !result.decompileCompleted()
                || result.getDecompiledFunction() == null) {
            writeLine("DECOMPILATION_INCOMPLETE");
        }
        else {
            writeLine(result.getDecompiledFunction().getC());
        }
        writeLine("=== END FUNCTION ===");
        writeLine("");
    }

    private Address address(String value) throws Exception {
        return currentProgram.getAddressFactory()
            .getDefaultAddressSpace().getAddress(value);
    }

    private void writeLine(String value) throws Exception {
        output.write(value);
        output.newLine();
    }
}
