import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
public class TraceDictionaryUse extends GhidraScript {
 StringBuilder out = new StringBuilder();
 void line(Object s) { out.append(s).append("\n"); }
 Address a(String s) throws Exception { return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(s); }
 void refs(Address target) throws Exception {
  line("REFS TO " + target);
  ReferenceIterator it = currentProgram.getReferenceManager().getReferencesTo(target);
  while(it.hasNext()) { Reference r=it.next(); Function f=getFunctionContaining(r.getFromAddress()); line(r+" FUNCTION="+(f==null?"none":f.getEntryPoint()));
   if(f!=null) { Instruction p=getInstructionAt(r.getFromAddress()); if(p!=null) { for(int i=0;i<4 && p.getPrevious()!=null;i++)p=p.getPrevious(); for(int i=0;i<10 && p!=null;i++,p=p.getNext())line(p.getAddress()+" "+p); } }
  }
 }
 public void run() throws Exception {
  String[] args=getScriptArgs(); DecompInterface d=new DecompInterface(); d.openProgram(currentProgram);
  try { for(int n=1;n<args.length;n++) {
   String[] arg=args[n].split(":");
   if(arg[0].equals("symrefs")) { for(Symbol sym:currentProgram.getSymbolTable().getGlobalSymbols(arg[1])) { line("SYMBOL " + sym.getName() + " " + sym.getAddress()); refs(sym.getAddress()); Function sf=getFunctionAt(sym.getAddress()); if(sf!=null) { Address[] ts=sf.getFunctionThunkAddresses(true); if(ts!=null) for(Address t:ts) refs(t); } } continue; }
   Address addr=a(arg[1]);
   if(arg[0].equals("refs"))refs(addr);
   if(arg[0].equals("bytes")) { byte[] b=new byte[128]; currentProgram.getMemory().getBytes(addr,b); line("BYTES " + addr + " " + java.util.HexFormat.of().formatHex(b)); line("TEXT " + new String(b,StandardCharsets.UTF_8)); }
   if(arg[0].equals("ptr")) { for(int i=-4;i<=16;i++){Address slot=addr.add(i*8); long v=currentProgram.getMemory().getLong(slot); Address t=addr.getAddressSpace().getAddress(v); Function f=getFunctionAt(t); line("SLOT "+slot+" -> "+t+" "+(f==null?"":f.getName()));} }
   if(arg[0].equals("slotdec")) { line("RESOLVED SLOT " + addr); addr=addr.getAddressSpace().getAddress(currentProgram.getMemory().getLong(addr)); arg[0]="dec"; }
   if(arg[0].equals("dec")) {Function f=getFunctionAt(addr);line("FUNCTION "+addr); if(f!=null){DecompileResults r=d.decompileFunction(f,60,monitor); line(r.decompileCompleted()?r.getDecompiledFunction().getC():r.getErrorMessage());}}
  } line("REPORT_COMPLETE"); Files.writeString(Paths.get(args[0]),out.toString(),StandardCharsets.UTF_8); } finally {d.dispose();}
 }
}