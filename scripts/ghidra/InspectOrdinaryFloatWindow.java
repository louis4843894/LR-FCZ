import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Instruction;
import java.nio.file.*;
public class InspectOrdinaryFloatWindow extends GhidraScript {
 public void run() throws Exception {
  if(!currentProgram.getName().equals("libgame-12.4.2-pull.so"))throw new IllegalArgumentException("wrong module");
  StringBuilder out=new StringBuilder("Verified ordinary GearStat floating-point window; read-only listing, no analysis.\n");
  var space=currentProgram.getAddressFactory().getDefaultAddressSpace();
  for(long pc=0x122e170L;pc<0x122e1b0L;pc+=4){Instruction in=getInstructionAt(space.getAddress(pc));out.append(Long.toHexString(pc)).append(" ").append(in==null?"NO_INSTRUCTION":in).append("\n");}
  Files.writeString(Paths.get(getScriptArgs()[0]),out.toString());
 }
}
