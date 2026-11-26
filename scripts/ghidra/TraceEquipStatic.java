import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
public class TraceEquipStatic extends GhidraScript {
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
   if(arg[0].equals("joint")) {
    java.util.Set<Address> first=new java.util.LinkedHashSet<>(),second=new java.util.LinkedHashSet<>();
    for(int targetIndex=1;targetIndex<=2;targetIndex++) {
     ReferenceIterator refs=currentProgram.getReferenceManager().getReferencesTo(a(arg[targetIndex]));
     while(refs.hasNext()) {Function f=getFunctionContaining(refs.next().getFromAddress());if(f!=null)(targetIndex==1?first:second).add(f.getEntryPoint());}
    }
    line("FIRST_CALLERS "+first);line("SECOND_CALLERS "+second);first.retainAll(second);line("JOINT_CALLERS "+first);
    int selected=0;for(Address entry:first) {if(selected++>=3)break;Function f=getFunctionAt(entry);line("FUNCTION "+entry);DecompileResults r=d.decompileFunction(f,60,monitor);line(r.decompileCompleted()?r.getDecompiledFunction().getC():r.getErrorMessage());}
    continue;
   }
   if(arg[0].equals("gearslot")) {
    java.util.Set<Address> selected=new java.util.LinkedHashSet<>();
    ghidra.program.model.address.AddressSet region=new ghidra.program.model.address.AddressSet(a("01218000"),a("01230000"));
    ghidra.program.model.listing.InstructionIterator instructions=currentProgram.getListing().getInstructions(region,true);
    while(instructions.hasNext()) { Instruction in=instructions.next(); if(in.toString().contains("#0x1d8")) { Function f=getFunctionContaining(in.getAddress()); if(f!=null) {line("GRADE_ATTR_SLOT_CONTEXT "+in.getAddress()+" "+in+" FUNCTION="+f.getEntryPoint());selected.add(f.getEntryPoint());} } }
    int slotCount=0;for(Address entry:selected) {if(slotCount++>=10)break;Function f=getFunctionAt(entry);line("FUNCTION "+entry);DecompileResults r=d.decompileFunction(f,60,monitor);line(r.decompileCompleted()?r.getDecompiledFunction().getC():r.getErrorMessage());}continue;
   }
   if(arg[0].equals("gearfield")) {
    java.util.Set<Address> selected=new java.util.LinkedHashSet<>();
    ghidra.program.model.address.AddressSet region=new ghidra.program.model.address.AddressSet(a("0121dca4"),a("01228000"));
    ghidra.program.model.listing.InstructionIterator instructions=currentProgram.getListing().getInstructions(region,true);
    while(instructions.hasNext()) { Instruction in=instructions.next();String text=in.toString();if(text.startsWith("ldr w") && text.contains(", #0xd8]") && !text.contains("[sp")) {Function f=getFunctionContaining(in.getAddress());if(f!=null){line("EQUIP_FIELD_CONTEXT "+in.getAddress()+" "+in+" FUNCTION="+f.getEntryPoint());selected.add(f.getEntryPoint());}}}
    int fieldCount=0;for(Address entry:selected) {if(fieldCount++>=6)break;Function f=getFunctionAt(entry);line("FUNCTION "+entry);DecompileResults r=d.decompileFunction(f,60,monitor);line(r.decompileCompleted()?r.getDecompiledFunction().getC():r.getErrorMessage());}continue;
   }
   Address addr=a(arg[1]);
   if(arg[0].equals("refs"))refs(addr);
   if(arg[0].equals("refdec")) { line("IMAGE_BASE " + currentProgram.getImageBase()); refs(addr); java.util.Set<Address> done=new java.util.LinkedHashSet<>(); ReferenceIterator ri=currentProgram.getReferenceManager().getReferencesTo(addr); while(ri.hasNext()) { Function f=getFunctionContaining(ri.next().getFromAddress()); if(f!=null && done.add(f.getEntryPoint()) && done.size()<=8) { line("FUNCTION " + f.getEntryPoint()); DecompileResults r=d.decompileFunction(f,60,monitor); line(r.decompileCompleted()?r.getDecompiledFunction().getC():r.getErrorMessage()); } } }
   if(arg[0].equals("bytes")) { byte[] b=new byte[128]; currentProgram.getMemory().getBytes(addr,b); line("BYTES " + addr + " " + java.util.HexFormat.of().formatHex(b)); line("TEXT " + new String(b,StandardCharsets.UTF_8)); }
   if(arg[0].equals("ptr")) { for(int i=-4;i<=16;i++){Address slot=addr.add(i*8); long v=currentProgram.getMemory().getLong(slot); Address t=addr.getAddressSpace().getAddress(v); Function f=getFunctionAt(t); line("SLOT "+slot+" -> "+t+" "+(f==null?"":f.getName()));} }
   if(arg[0].equals("slotdec")) { line("RESOLVED SLOT " + addr); addr=addr.getAddressSpace().getAddress(currentProgram.getMemory().getLong(addr)); arg[0]="dec"; }
   if(arg[0].equals("callsdec")) { java.util.Set<Address> q=new java.util.LinkedHashSet<>(); q.add(addr); for(int level=0;level<2;level++) { java.util.List<Address> levelQ=new java.util.ArrayList<>(q); for(Address t:levelQ) { Function ff=getFunctionAt(t); if(ff==null)continue; ghidra.program.model.listing.InstructionIterator ii=currentProgram.getListing().getInstructions(ff.getBody(),true); while(ii.hasNext()) { Instruction in=ii.next(); if(!in.getFlowType().isCall())continue; for(Address dest:in.getFlows()) if(dest.getOffset()>=0x019c3000L && dest.getOffset()<0x019c8000L)q.add(dest); } } } for(Address t:q) { Function ff=getFunctionAt(t); if(ff!=null) { line("FUNCTION "+t); DecompileResults r=d.decompileFunction(ff,60,monitor); line(r.decompileCompleted()?r.getDecompiledFunction().getC():r.getErrorMessage()); } } }
   if(arg[0].equals("dec")) {Function f=getFunctionAt(addr);
    // The updated binary is imported without auto-analysis. Define only the
    // explicitly requested target in that separate version project.
    if(f==null && currentProgram.getName().equals("libgame-12.4.2-pull.so")) {
     new ghidra.app.cmd.disassemble.DisassembleCommand(addr,new AddressSet(addr,addr.add(0x4000)),true).applyTo(currentProgram,monitor);
     f=createFunction(addr,"target_"+addr);
    }
    line("FUNCTION "+addr); if(f!=null){DecompileResults r=d.decompileFunction(f,60,monitor); line(r.decompileCompleted()?r.getDecompiledFunction().getC():r.getErrorMessage());}}
  } line("REPORT_COMPLETE"); Files.writeString(Paths.get(args[0]),out.toString(),StandardCharsets.UTF_8); } finally {d.dispose();}
 }
}
