import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Instruction;
import java.nio.file.*;
public class DumpNativeInstructions extends GhidraScript {
 public void run() throws Exception {
  if(!currentProgram.getName().equals("libgame-12.4.2-pull.so"))throw new IllegalArgumentException("wrong module");
  String[] args=getScriptArgs();StringBuilder out=new StringBuilder("Read-only explicit instruction windows; no auto-analysis.\n");
  var space=currentProgram.getAddressFactory().getDefaultAddressSpace();
  for(int i=1;i<args.length;i++){
   String[] span=args[i].split(":");long from=Long.parseLong(span[0],16),to=Long.parseLong(span[1],16);
   if(to<=from||to-from>4096||(from&3)!=0||(to&3)!=0)throw new IllegalArgumentException("bounded aligned window required");
   out.append("WINDOW ").append(args[i]).append("\n");
   for(long pc=from;pc<to;pc+=4){Instruction in=getInstructionAt(space.getAddress(pc));out.append(Long.toHexString(pc)).append(" ").append(in==null?"NO_INSTRUCTION":in).append("\n");}
  }
  Files.writeString(Paths.get(args[0]),out.toString());
 }
}
