import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import java.nio.file.*;
public class RepairGuildSkillPlusTarget extends GhidraScript {
 public void run() throws Exception {
  if(!currentProgram.getName().equals("libgame-12.4.2-pull.so"))throw new IllegalArgumentException("wrong module");
  var space=currentProgram.getAddressFactory().getDefaultAddressSpace();
  // Explicit .eh_frame_hdr interval, checked against the same module SHA.
  Address bad=space.getAddress(0x122b35cL),start=space.getAddress(0x122b340L),end=space.getAddress(0x122b36bL);
  Function accidental=getFunctionAt(bad);
  if(accidental!=null){
   if(!accidental.getName().equals("target_0122b35c"))throw new IllegalStateException("preserve other analyst changes");
   currentProgram.getFunctionManager().removeFunction(bad);
  }
  Function real=getFunctionAt(start);
  if(real==null){disassemble(start);real=createFunction(start,"target_0122b340");}
  if(real==null)throw new IllegalStateException("could not restore verified function");
  real.setBody(new AddressSet(start,end));
  Files.writeString(Paths.get(getScriptArgs()[0]),"Removed only accidental target_0122b35c. Restored ELF unwind interval [0122b340,0122b36c). No auto-analysis.\n");
 }
}
