// Exports one saved decompilation and embeds the existing caller evidence.
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
import java.util.List;

public class ExportDecodeEvidence extends GhidraScript {
    private static final String TARGET_ENTRY = "01a41d38";
    private static final String CALLER_HEADING =
        "FUNCTION: FUN_01a2053c entry=01a2053c";
    private static final String CALLER_CALLS_HEADING =
        "DIRECT_CALLS_FROM: 01a2053c";

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) {
            throw new IllegalArgumentException(
                "Usage: ExportDecodeEvidence.java <output-path> <existing-caller-report>");
        }

        Path outputPath = Paths.get(args[0]);
        Path callerReportPath = Paths.get(args[1]);
        if (!Files.isRegularFile(callerReportPath)) {
            throw new IllegalStateException(
                "Existing caller evidence report is missing: " + callerReportPath);
        }

        try (BufferedWriter output = Files.newBufferedWriter(
                outputPath, StandardCharsets.UTF_8)) {
            output.write("Source project: " + currentProgram.getName());
            output.newLine();
            output.write("Analysis: saved project only; auto-analysis disabled");
            output.newLine();
            output.write("Existing caller report: " + callerReportPath);
            output.newLine();
            output.newLine();

            writeExistingCaller(output, callerReportPath);
            writeTargetFunction(output);
            writeIndirectCallSites(output);

            output.write("DB ASSOCIATION: 尚未建立關聯。");
            output.newLine();
            output.write(
                "The examined caller and target-function evidence does not directly "
                + "identify game_item_equip.db.");
            output.newLine();
            output.write("REPORT_COMPLETE");
            output.newLine();
        }
    }

    private void writeExistingCaller(BufferedWriter output, Path source)
            throws Exception {
        List<String> lines = Files.readAllLines(source, StandardCharsets.UTF_8);
        int start = -1;
        for (int i = 0; i < lines.size(); i++) {
            if (lines.get(i).equals(CALLER_HEADING)) {
                start = i;
                break;
            }
        }
        if (start < 0) {
            throw new IllegalStateException(
                "Existing caller function was not found in " + source);
        }
        int end = -1;
        for (int i = start + 1; i < lines.size(); i++) {
            if (lines.get(i).equals(CALLER_CALLS_HEADING)) {
                end = i;
                break;
            }
        }
        if (end < 0) {
            throw new IllegalStateException(
                "Existing caller direct-call section was not found in " + source);
        }

        output.write("=== EXISTING CALLER: FUN_01a2053c ===");
        output.newLine();
        for (int i = start; i < end; i++) {
            output.write(lines.get(i));
            output.newLine();
        }
        output.write("=== END EXISTING CALLER ===");
        output.newLine();
        output.newLine();
    }

    private void writeTargetFunction(BufferedWriter output) throws Exception {
        Address address = currentProgram.getAddressFactory()
            .getDefaultAddressSpace().getAddress(TARGET_ENTRY);
        Function function = currentProgram.getFunctionManager().getFunctionAt(address);
        if (function == null) {
            throw new IllegalStateException(
                "Target function not found in saved project at " + TARGET_ENTRY);
        }

        DecompInterface decompiler = new DecompInterface();
        if (!decompiler.openProgram(currentProgram)) {
            throw new IllegalStateException(
                "Could not open saved Ghidra program for decompilation");
        }
        try {
            DecompileResults result = decompiler.decompileFunction(function, 90, monitor);
            if (result == null || !result.decompileCompleted()
                    || result.getDecompiledFunction() == null) {
                throw new IllegalStateException(
                    "Decompilation did not complete for " + TARGET_ENTRY);
            }
            output.write("=== TARGET FUNCTION: " + function.getName()
                + " entry=" + function.getEntryPoint() + " ===");
            output.newLine();
            output.write(result.getDecompiledFunction().getC());
            output.newLine();
            output.write("=== END TARGET FUNCTION ===");
            output.newLine();
            output.newLine();
        }
        finally {
            decompiler.dispose();
        }
    }

    private void writeIndirectCallSites(BufferedWriter output) throws Exception {
        Address address = currentProgram.getAddressFactory()
            .getDefaultAddressSpace().getAddress(TARGET_ENTRY);
        Function function = currentProgram.getFunctionManager().getFunctionAt(address);
        boolean found = false;
        output.write("=== INDIRECT CALL SITES IN FUN_01a41d38 ===");
        output.newLine();
        for (Instruction instruction :
                currentProgram.getListing().getInstructions(function.getBody(), true)) {
            String mnemonic = instruction.getMnemonicString();
            if (!mnemonic.startsWith("blr")) {
                continue;
            }
            found = true;
            output.write("CALL_SITE: " + instruction.getAddress()
                + " instruction=" + instruction);
            output.newLine();
            Reference[] references = currentProgram.getReferenceManager()
                .getReferencesFrom(instruction.getAddress());
            if (references.length == 0) {
                output.write("TARGET: unresolved in saved references");
                output.newLine();
            }
            else {
                for (Reference reference : references) {
                    Function target = currentProgram.getFunctionManager()
                        .getFunctionAt(reference.getToAddress());
                    output.write("REFERENCE: type=" + reference.getReferenceType()
                        + " target=" + reference.getToAddress()
                        + " function="
                        + (target == null ? "<no function>" : target.getName()));
                    output.newLine();
                }
            }
        }
        if (!found) {
            output.write("No BLR indirect-call instruction identified in the listing.");
            output.newLine();
        }
        output.write("=== END INDIRECT CALL SITES ===");
        output.newLine();
        output.newLine();
    }
}
