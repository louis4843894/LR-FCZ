import ghidra.app.script.GhidraScript;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
public class ServeNativeEvidence extends GhidraScript {
 public void run() throws Exception {
  String[] args=getScriptArgs();Path queue=Paths.get(args[0]).toAbsolutePath().normalize();
  Path reports=Paths.get(args[1]).toAbsolutePath().normalize();Files.createDirectories(queue);
  long end=System.currentTimeMillis()+900000;
  Files.writeString(queue.resolve("ready"),currentProgram.getName(),StandardCharsets.UTF_8);
  while(!monitor.isCancelled()&&System.currentTimeMillis()<end&&!Files.exists(queue.resolve("stop"))) {
   List<Path> jobs;
   try(var stream=Files.list(queue)){jobs=stream.filter(p->p.toString().endsWith(".req")).sorted().toList();}
   if(jobs.isEmpty()){Thread.sleep(250);continue;}
   for(Path job:jobs) {
    Path running=job.resolveSibling(job.getFileName()+".running");Files.move(job,running);
    try {
     List<String> lines=Files.readAllLines(running,StandardCharsets.UTF_8);
     if(lines.size()<2||lines.size()>25)throw new IllegalArgumentException("job bound");
     Path target=Paths.get(lines.get(0)).toAbsolutePath().normalize();
     if(!target.startsWith(reports))throw new IllegalArgumentException("report path outside workspace");
     for(String line:lines.subList(1,lines.size()))if(!line.matches("(dec|slotdec|refs|ptr|bytes):[0-9a-fA-F]{6,16}|joint:[0-9a-fA-F]{6,16}:[0-9a-fA-F]{6,16}"))throw new IllegalArgumentException("explicit target operations only");
     runScript("TraceEquipStatic.java",lines.toArray(String[]::new));
     Files.writeString(job.resolveSibling(job.getFileName()+".done"),"ok",StandardCharsets.UTF_8);
     println("EVIDENCE_JOB_DONE "+job.getFileName());
    } catch(Exception error){Files.writeString(job.resolveSibling(job.getFileName()+".error"),error.toString(),StandardCharsets.UTF_8);println("EVIDENCE_JOB_ERROR "+error);}
   }
  }
  Files.writeString(queue.resolve("closed"),"closed",StandardCharsets.UTF_8);
 }
}
