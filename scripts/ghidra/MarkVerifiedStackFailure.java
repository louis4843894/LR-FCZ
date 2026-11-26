import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

/** Correct one proven PLT annotation in the targeted 12.4.2 project.
 * ELF relocation at 01fbd240 names __stack_chk_fail (JUMP_SLOT).
 * No auto-analysis, runtime changes, or guessed function signatures.
 */
public class MarkVerifiedStackFailure extends GhidraScript {
    public void run() throws Exception {
        if (!currentProgram.getName().equals("libgame-12.4.2-pull.so"))
            throw new IllegalArgumentException("verified module only");
        Address address = toAddr(0x01dd9c50L);
        byte[] expected = java.util.HexFormat.of().parseHex("300f0090112241f91002099120021fd6");
        byte[] actual = new byte[16];
        currentProgram.getMemory().getBytes(address, actual);
        if (!java.util.Arrays.equals(expected, actual))
            throw new IllegalArgumentException("verified stack-failure PLT bytes differ");
        Function function = getFunctionAt(address);
        if (function == null) {
            disassemble(address);
            function = createFunction(address, "verified_stack_chk_fail_plt");
        }
        if (function == null) throw new IllegalStateException("PLT function unavailable");
        function.setNoReturn(true);
        println("Verified __stack_chk_fail PLT marked noreturn at " + address);
    }
}
