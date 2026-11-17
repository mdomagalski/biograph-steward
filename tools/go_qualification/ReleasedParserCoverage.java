/*
 * Publish coverage from the released GAFeRence parser, without reimplementing it.
 * This class performs no reasoning and creates no satisfiability/pass labels.
 * Compile/run with the exact released GAFeRence lib/* on the class path.
 */
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.geneontology.gaferencer.ExtendedAnnotation;
import org.geneontology.gaferencer.Gaferencer$;
import org.geneontology.gaferencer.Link;
import org.geneontology.gaferencer.MultiCurieUtil;
import org.geneontology.gaferencer.TermWithTaxon;
import org.prefixcommons.CurieUtil;
import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.model.OWLObjectProperty;
import org.semanticweb.owlapi.model.OWLOntology;
import scala.Tuple2;

public final class ReleasedParserCoverage {
    private static Map<String, Object> link(Link value) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("relation", value.relation().getIRI().toString());
        result.put("term", value.target().getIRI().toString());
        return result;
    }

    private static Map<String, Object> key(ExtendedAnnotation value) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("annotation", link(value.annotation()));
        result.put("taxon", value.taxon().getIRI().toString());
        List<Map<String, Object>> extension = new ArrayList<>();
        scala.collection.Iterator<Link> iterator = value.extension().iterator();
        while (iterator.hasNext()) extension.add(link(iterator.next()));
        result.put("extension", extension);
        return result;
    }

    private static String sha(String value) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
        StringBuilder result = new StringBuilder();
        for (byte part : digest) result.append(String.format("%02x", part & 0xff));
        return result.toString();
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 5) {
            throw new IllegalArgumentException("Expected ontology.owl input.gaf go_context.jsonld obo_context.jsonld output.jsonl");
        }
        OWLOntology ontology = OWLManager.createOWLOntologyManager().loadOntologyFromOntologyDocument(new File(args[0]));
        List<CurieUtil> contexts = new ArrayList<>();
        contexts.add(CurieUtil.fromJsonLdFile(new File(args[2]).getAbsolutePath()));
        contexts.add(CurieUtil.fromJsonLdFile(new File(args[3]).getAbsolutePath()));
        MultiCurieUtil curie = new MultiCurieUtil(scala.jdk.javaapi.CollectionConverters.asScala(contexts).toList());
        scala.collection.immutable.Map<String, OWLObjectProperty> properties = Gaferencer$.MODULE$.indexPropertiesByName(ontology);
        ObjectMapper mapper = new ObjectMapper();
        long number = 0;
        long records = 0;
        try (BufferedReader input = Files.newBufferedReader(Paths.get(args[1]), StandardCharsets.UTF_8);
             BufferedWriter output = Files.newBufferedWriter(Paths.get(args[4]), StandardCharsets.UTF_8)) {
            String line;
            while ((line = input.readLine()) != null) {
                number++;
                if (line.startsWith("!")) continue;
                scala.collection.immutable.Set<Tuple2<TermWithTaxon, ExtendedAnnotation>> parsed =
                    Gaferencer$.MODULE$.processLine(line, properties, curie);
                List<Map<String, Object>> keys = new ArrayList<>();
                scala.collection.Iterator<Tuple2<TermWithTaxon, ExtendedAnnotation>> iterator = parsed.iterator();
                while (iterator.hasNext()) keys.add(key(iterator.next()._2()));
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("gaf_line", number);
                row.put("raw_line_sha256", sha(line));
                row.put("released_parser_keys", keys);
                output.write(mapper.writeValueAsString(row));
                output.newLine();
                records++;
            }
        }
        System.out.println("Released parser coverage records: " + records);
    }
}
