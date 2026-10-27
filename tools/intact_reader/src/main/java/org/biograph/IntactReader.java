package org.biograph;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import psidev.psi.mi.jami.datasource.FileSourceContext;
import psidev.psi.mi.jami.datasource.FileSourceLocator;
import psidev.psi.mi.jami.model.*;
import psidev.psi.mi.jami.tab.extension.MitabFeature;
import psidev.psi.mi.jami.tab.extension.MitabSourceLocator;
import psidev.psi.mi.jami.tab.extension.datasource.MitabEvidenceStreamSource;
import psidev.psi.mi.jami.tab.io.parser.InteractionEvidenceLineParser;
import psidev.psi.mi.jami.tab.io.parser.MitabLineParserConstants;
import psidev.psi.mi.jami.tab.io.parser.TokenMgrError;
import psidev.psi.mi.jami.tab.listener.MitabParserListener;
import psidev.psi.mi.jami.utils.CvTermUtils;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.PrintStream;
import java.io.StringReader;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.IdentityHashMap;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Local, row-accounted projection of the unmodified official JAMI evidence reader.
 * No source selection, eligibility grading, ontology enrichment or truth inference.
 */
public final class IntactReader {
    private static final Gson JSON = new GsonBuilder().serializeNulls().disableHtmlEscaping().create();
    private static final String FORMAT = "biograph-steward.intact-jami-row.v1";

    private IntactReader() { }

    private static Map<String, Object> map(Object... pairs) {
        Map<String, Object> value = new LinkedHashMap<>();
        for (int index = 0; index < pairs.length; index += 2) {
            value.put((String) pairs[index], pairs[index + 1]);
        }
        return value;
    }

    private static Map<String, Object> term(CvTerm value) {
        return value == null ? null : map("mi_id", value.getMIIdentifier(),
                "mod_id", value.getMODIdentifier(), "par_id", value.getPARIdentifier(),
                "name", value.getShortName(), "full_name", value.getFullName());
    }

    private static Map<String, Object> xref(Xref value) {
        return value == null ? null : map("database", term(value.getDatabase()), "id", value.getId(),
                "version", value.getVersion(), "qualifier", term(value.getQualifier()));
    }

    private static List<Object> xrefs(Collection<? extends Xref> values) {
        List<Object> result = new ArrayList<>();
        if (values != null) for (Xref value : values) result.add(xref(value));
        return result;
    }

    private static List<Object> terms(Collection<? extends CvTerm> values) {
        List<Object> result = new ArrayList<>();
        if (values != null) for (CvTerm value : values) result.add(term(value));
        return result;
    }

    private static List<Object> aliases(Collection<? extends Alias> values) {
        List<Object> result = new ArrayList<>();
        if (values != null) for (Alias value : values) {
            result.add(map("type", term(value.getType()), "name", value.getName()));
        }
        return result;
    }

    private static List<Object> annotations(Collection<? extends Annotation> values) {
        List<Object> result = new ArrayList<>();
        if (values != null) for (Annotation value : values) {
            result.add(map("topic", term(value.getTopic()), "value", value.getValue()));
        }
        return result;
    }

    private static String cell(String[] raw, int index) {
        return index >= 0 && index < raw.length ? raw[index] : null;
    }

    private static Map<String, Object> position(Position value) {
        return value == null ? null : map("status", term(value.getStatus()),
                "start", value.getStart(), "end", value.getEnd(),
                "undetermined", value.isPositionUndetermined());
    }

    private static List<Object> features(Collection<? extends Feature<?, ?>> values, int line) {
        List<Object> result = new ArrayList<>();
        if (values != null) for (Feature<?, ?> value : values) {
            List<Object> ranges = new ArrayList<>();
            for (Range range : value.getRanges()) {
                ranges.add(map("start", position(range.getStart()), "end", position(range.getEnd()),
                        "linked", range.isLink()));
            }
            result.add(map("type", term(value.getType()), "name", value.getShortName(),
                    "full_name", value.getFullName(), "text",
                    value instanceof MitabFeature ? ((MitabFeature<?, ?>) value).getText() : null,
                    "interpro", value.getInterpro(), "ranges", ranges,
                    "identifiers", xrefs(value.getIdentifiers()), "xrefs", xrefs(value.getXrefs()),
                    "annotations", annotations(value.getAnnotations()), "source_locator", locator(value, line)));
        }
        return result;
    }

    private static Map<String, Object> locator(Object value, int physicalLine) {
        if (!(value instanceof FileSourceContext)) return null;
        FileSourceLocator source = ((FileSourceContext) value).getSourceLocator();
        if (source == null) return null;
        return map("line_number", physicalLine, "parser_line_number", source.getLineNumber(),
                "character_number", source.getCharNumber(), "mitab_column",
                source instanceof MitabSourceLocator ? ((MitabSourceLocator) source).getColumnNumber() : null);
    }

    private static void locators(Object value, int line, List<Object> result,
                                 IdentityHashMap<Object, Boolean> seen) {
        if (value == null || seen.put(value, Boolean.TRUE) != null) return;
        Map<String, Object> source = locator(value, line);
        if (source != null) result.add(source);
        if (value instanceof Collection<?>) {
            for (Object item : (Collection<?>) value) locators(item, line, result, seen);
        }
    }

    private static Map<String, Object> participant(ParticipantEvidence value, String[] raw, int line) {
        Map<String, Object> source = locator(value, line);
        Integer column = source == null ? null : (Integer) source.get("mitab_column");
        String side = column != null && column == 1 ? "A" : column != null && column == 2 ? "B" : null;
        int offset = "A".equals(side) ? 0 : "B".equals(side) ? 1 : -1;
        Interactor molecule = value.getInteractor();
        Stoichiometry count = value.getStoichiometry();
        return map("side", side, "source_locator", source,
                "unique_id_raw", offset < 0 ? null : cell(raw, offset),
                "alternative_ids_raw", offset < 0 ? null : cell(raw, 2 + offset),
                "type_raw", offset < 0 ? null : cell(raw, 20 + offset),
                "preferred_id", molecule == null ? null : xref(molecule.getPreferredIdentifier()),
                "identifiers", molecule == null ? new ArrayList<>() : xrefs(molecule.getIdentifiers()),
                "aliases", molecule == null ? new ArrayList<>() : aliases(molecule.getAliases()),
                "participant_aliases", aliases(value.getAliases()),
                "taxid", molecule == null || molecule.getOrganism() == null ? null : molecule.getOrganism().getTaxId(),
                "interactor_type", molecule == null ? null : term(molecule.getInteractorType()),
                "biological_role", term(value.getBiologicalRole()),
                "experimental_role", term(value.getExperimentalRole()),
                "identification_methods", terms(value.getIdentificationMethods()),
                "features", features(value.getFeatures(), line),
                "stoichiometry", count == null ? null : map("min", count.getMinValue(), "max", count.getMaxValue()),
                "annotations", annotations(value.getAnnotations()), "xrefs", xrefs(value.getXrefs()));
    }

    private static Map<String, Object> interaction(InteractionEvidence value, String[] raw, int line) {
        Experiment experiment = value.getExperiment();
        Publication publication = experiment == null ? null : experiment.getPublication();
        Source source = publication == null ? null : publication.getSource();
        List<Object> sources = new ArrayList<>();
        if (source != null) sources.add(term(source));
        List<Object> participants = new ArrayList<>();
        for (ParticipantEvidence item : value.getParticipants()) {
            participants.add(participant(item, raw, line));
        }
        return map("source_locator", locator(value, line), "negative", value.isNegative(),
                "negative_raw", cell(raw, 35), "expansion_raw", cell(raw, 15),
                "detection_method", experiment == null ? null : term(experiment.getInteractionDetectionMethod()),
                "interaction_type", term(value.getInteractionType()),
                "host_taxid", experiment == null || experiment.getHostOrganism() == null ? null : experiment.getHostOrganism().getTaxId(),
                "publication_ids", publication == null ? new ArrayList<>() : xrefs(publication.getIdentifiers()),
                "pubmed_id", publication == null ? null : publication.getPubmedId(),
                "doi", publication == null ? null : publication.getDoi(),
                "publication_imex_id", publication == null ? null : publication.getImexId(),
                "source_ids", sources, "evidence_ids", xrefs(value.getIdentifiers()),
                "imex_id", value.getImexId(), "annotations", annotations(value.getAnnotations()),
                "xrefs", xrefs(value.getXrefs()), "participants", participants);
    }

    private static MitabParserListener listener(List<Object> diagnostics, int line, String phase) {
        return (MitabParserListener) Proxy.newProxyInstance(MitabParserListener.class.getClassLoader(),
                new Class<?>[]{MitabParserListener.class}, (proxy, method, args) -> {
                    if (method.getDeclaringClass() == Object.class) {
                        if (method.getName().equals("hashCode")) return System.identityHashCode(proxy);
                        if (method.getName().equals("equals")) return proxy == args[0];
                        return "capturing-MitabParserListener";
                    }
                    List<Object> classes = new ArrayList<>();
                    List<Object> argumentValues = new ArrayList<>();
                    List<Object> sources = new ArrayList<>();
                    List<Object> messages = new ArrayList<>();
                    if (args != null) for (Object arg : args) {
                        classes.add(arg == null ? null : arg.getClass().getName());
                        argumentValues.add(arg == null || arg instanceof String || arg instanceof Number
                                || arg instanceof Boolean ? arg : null);
                        locators(arg, line, sources, new IdentityHashMap<>());
                        if (arg instanceof String) messages.add(arg);
                        if (arg instanceof Throwable) {
                            Throwable error = (Throwable) arg;
                            messages.add(error.getClass().getName() + ": " + error.getMessage());
                        }
                    }
                    if ((method.getName().equals("onEmptyUniqueIdentifiers")
                            || method.getName().equals("onMissingInteractorIdentifierColumns"))
                            && args != null && args.length == 3
                            && args[0] instanceof Number && args[1] instanceof Number && args[2] instanceof Number) {
                        sources.add(map("line_number", line, "parser_line_number", args[0],
                                "character_number", args[1], "mitab_column", args[2]));
                    }
                    diagnostics.add(map("phase", phase, "callback", method.getName(), "arg_classes", classes,
                            "argument_values", argumentValues,
                            "public_message", messages.isEmpty() ? null : String.join("; ",
                            messages.stream().map(String::valueOf).toArray(String[]::new)),
                            "source_locator", sources.isEmpty() ? null : sources.get(0),
                            "source_locators", sources));
                    return null;
                });
    }

    private static Map<String, Object> bridgeDiagnostic(String callback, String message, int line) {
        return map("phase", "bridge", "callback", callback, "arg_classes", new ArrayList<>(),
                "public_message", message,
                "source_locator", map("line_number", line, "parser_line_number", null,
                        "character_number", null, "mitab_column", null),
                "source_locators", new ArrayList<>());
    }

    @FunctionalInterface
    private interface FieldReader {
        Collection<?> read(InteractionEvidenceLineParser parser) throws Exception;
    }

    private static Object sourceValue(Object value) {
        if (value instanceof Xref) return xref((Xref) value);
        if (value instanceof CvTerm) return term((CvTerm) value);
        if (value instanceof Organism) {
            Organism organism = (Organism) value;
            return map("taxid", organism.getTaxId(), "scientific_name", organism.getScientificName(),
                    "common_name", organism.getCommonName());
        }
        if (value instanceof Annotation) {
            Annotation annotation = (Annotation) value;
            return map("topic", term(annotation.getTopic()), "value", annotation.getValue());
        }
        throw new IllegalArgumentException("Unsupported official field value class: " + value.getClass().getName());
    }

    private static Map<String, Object> field(String raw, int column, int line, FieldReader read) {
        List<Object> diagnostics = new ArrayList<>();
        List<Object> values = new ArrayList<>();
        boolean failed = false;
        // Use the SAME official grammar routines as MitabLine(), before object initializers.
        InteractionEvidenceLineParser parser = new InteractionEvidenceLineParser(new StringReader(raw + "\t"));
        parser.setParserListener(listener(diagnostics, line, "source_field"));
        try {
            // MitabLine() consumes DASH before dispatching individual field routines.
            if (raw.equals("-")) {
                if (parser.getNextToken().kind != MitabLineParserConstants.DASH
                        || parser.getNextToken().kind != MitabLineParserConstants.COLUMN_SEPARATOR
                        || parser.getNextToken().kind != MitabLineParserConstants.EOF) {
                    throw new IllegalStateException("Official missing-cell token framing mismatch.");
                }
                return map("column", column, "raw", raw, "status", "missing",
                        "values", values, "diagnostics", diagnostics,
                        "parser_path", "official MitabLine DASH branch; no field term supplied");
            }
            for (Object value : read.read(parser)) values.add(sourceValue(value));
            int following = parser.getNextToken().kind;
            int end = parser.getNextToken().kind;
            if (following != MitabLineParserConstants.COLUMN_SEPARATOR || end != MitabLineParserConstants.EOF) {
                failed = true;
                diagnostics.add(bridgeDiagnostic("bridge_source_field_trailing_input",
                        "Official field routine did not consume the entire cell before its separator and EOF.", line));
            }
        } catch (Exception | LinkageError | TokenMgrError error) {
            failed = true;
            diagnostics.add(bridgeDiagnostic("bridge_source_field_error",
                    error.getClass().getName() + ": " + error.getMessage(), line));
        }
        String status = failed ? "invalid" : !diagnostics.isEmpty() ? "parsed_with_diagnostics" : "parsed";
        return map("column", column, "raw", raw, "status", status,
                "values", values, "diagnostics", diagnostics);
    }

    private static Map<String, Object> sourceFields(String[] raw, int line) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int offset = 0; offset < 2; offset++) {
            final int side = offset;
            String suffix = offset == 0 ? "_a" : "_b";
            result.put("primary_ids" + suffix, field(raw[side], side + 1, line,
                    parser -> parser.ids(CvTermUtils.getIdentity(), false, side + 1)));
            result.put("alternative_ids" + suffix, field(raw[side + 2], side + 3, line,
                    parser -> parser.ids(CvTermUtils.getSecondary(), false, side + 3)));
            result.put("taxa" + suffix, field(raw[side + 9], side + 10, line,
                    parser -> parser.taxId(side + 10)));
            result.put("biological_roles" + suffix, field(raw[side + 16], side + 17, line,
                    parser -> parser.cvTerms(side + 17)));
            result.put("experimental_roles" + suffix, field(raw[side + 18], side + 19, line,
                    parser -> parser.cvTerms(side + 19)));
            result.put("interactor_types" + suffix, field(raw[side + 20], side + 21, line,
                    parser -> parser.cvTerms(side + 21)));
            result.put("identification_methods" + suffix, field(raw[side + 40], side + 41, line,
                    parser -> parser.cvTerms(side + 41)));
        }
        result.put("detection_methods", field(raw[6], 7, line, parser -> parser.cvTerms(7)));
        result.put("publication_ids", field(raw[8], 9, line,
                parser -> parser.ids(CvTermUtils.getIdentity(), true, 9)));
        result.put("interaction_types", field(raw[11], 12, line, parser -> parser.cvTerms(12)));
        result.put("source_databases", field(raw[12], 13, line, InteractionEvidenceLineParser::sourceDbs));
        result.put("evidence_ids", field(raw[13], 14, line,
                parser -> parser.ids(CvTermUtils.getIdentity(), true, 14)));
        result.put("complex_expansion", field(raw[15], 16, line, InteractionEvidenceLineParser::complexExpansion));
        result.put("interaction_annotations", field(raw[27], 28, line, parser -> parser.annotations(28)));
        result.put("host_taxa", field(raw[28], 29, line, parser -> parser.taxId(29)));
        return result;
    }

    /** Exactly one output record per physical input line, including malformed lines. */
    private static Map<String, Object> readLine(String rawLine, int number) {
        String[] raw = rawLine.split("\t", -1);
        List<Object> diagnostics = new ArrayList<>();
        List<Object> interactions = new ArrayList<>();
        Map<String, Object> result = map("format", FORMAT, "reader", "PSI-JAMI jami-mitab 3.9.4",
                "line_number", number, "raw_line", rawLine, "raw_cells", Arrays.asList(raw),
                "mitab27_framing_valid", raw.length == 42,
                "row_status", null, "parsed_count", 0, "diagnostics", diagnostics,
                "interaction", null, "interactions", interactions, "source_fields", null);
        if (rawLine.isBlank()) {
            result.put("row_status", "blank");
            return result;
        }
        if (rawLine.startsWith("#")) {
            result.put("row_status", rawLine.startsWith("#ID(s) interactor A\t") ? "header" : "comment");
            return result;
        }
        if (raw.length != 42) {
            diagnostics.add(bridgeDiagnostic("bridge_invalid_column_count",
                    "Expected exactly 42 physical tab-delimited MITAB 2.7 cells; found " + raw.length + ".", number));
        }
        if (raw.length == 42) result.put("source_fields", sourceFields(raw, number));
        MitabEvidenceStreamSource source = null;
        boolean failed = false;
        try {
            source = new MitabEvidenceStreamSource(new StringReader(rawLine + "\n"));
            source.setFileParserListener(listener(diagnostics, number, "row_model"));
            Iterator<InteractionEvidence> iterator = source.getInteractionsIterator();
            while (iterator.hasNext()) {
                InteractionEvidence value = iterator.next();
                interactions.add(interaction(value, raw, number));
            }
        } catch (RuntimeException | LinkageError | TokenMgrError error) {
            failed = true;
            diagnostics.add(bridgeDiagnostic("bridge_reader_error",
                    error.getClass().getName() + ": " + error.getMessage(), number));
        } finally {
            if (source != null) try {
                source.close();
            } catch (RuntimeException error) {
                failed = true;
                diagnostics.add(bridgeDiagnostic("bridge_close_error",
                        error.getClass().getName() + ": " + error.getMessage(), number));
            }
        }
        result.put("parsed_count", interactions.size());
        if (interactions.size() == 1) result.put("interaction", interactions.get(0));
        boolean rowDiagnostics = diagnostics.stream().anyMatch(item ->
                "row_model".equals(((Map<?, ?>) item).get("phase")));
        String status = failed ? "reader_error" : interactions.size() == 1
                ? rowDiagnostics ? "parsed_with_diagnostics" : "parsed"
                : interactions.isEmpty() ? "unparsed" : "unexpected_multiple_interactions";
        result.put("official_reader_status", status);
        result.put("row_status", raw.length == 42 ? status : "invalid_column_count");
        return result;
    }

    public static void main(String[] args) throws IOException {
        if (args.length != 1) {
            throw new IllegalArgumentException("Usage: org.biograph.IntactReader LOCAL_MITAB_FILE (no URLs)");
        }
        Path input = Path.of(args[0]);
        if (!Files.isRegularFile(input)) throw new IllegalArgumentException("Input must be a local regular file.");
        final PrintStream jsonOutput = System.out;
        final PrintStream upstreamMessages = System.err;
        try (BufferedReader reader = Files.newBufferedReader(input, StandardCharsets.UTF_8)) {
            String line;
            int number = 0;
            while ((line = reader.readLine()) != null) {
                Map<String, Object> record;
                // Author error_skipToNext() prints ParseException prose to System.out.
                // This single-threaded CLI keeps it intact on stderr during official
                // field/row parsing, then restores the dedicated JSONL transport.
                try {
                    System.setOut(upstreamMessages);
                    record = readLine(line, ++number);
                } finally {
                    System.setOut(jsonOutput);
                }
                jsonOutput.println(JSON.toJson(record));
            }
        }
    }
}
