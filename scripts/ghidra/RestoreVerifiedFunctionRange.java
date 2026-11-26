import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import java.nio.file.*;
public class RestoreVerifiedFunctionRange extends GhidraScript {
 public void run() throws Exception {
  if(!currentProgram.getName().equals("libgame-12.4.2-pull.so"))throw new IllegalArgumentException("wrong module");
  var space=currentProgram.getAddressFactory().getDefaultAddressSpace();
  // Exact ELF unwind interval, verified offline: [0122db78,0122dde4).
  Address bad=space.getAddress(0x122dd04L),start=space.getAddress(0x122db78L),end=space.getAddress(0x122dde3L);
  Function accidental=getFunctionAt(bad);
  if(accidental!=null){if(!accidental.getName().equals("target_0122dd04"))throw new IllegalStateException("preserve other analyst changes");currentProgram.getFunctionManager().removeFunction(bad);}
  Function real=getFunctionAt(start);if(real==null)throw new IllegalStateException("verified original function missing");
  real.setBody(new AddressSet(start,end));
  Files.writeString(Paths.get(getScriptArgs()[0]),"Restored ELF unwind range 0122db78 <= pc < 0122dde4. Removed only accidental target_0122dd04. No auto-analysis.\n");
 }
}
