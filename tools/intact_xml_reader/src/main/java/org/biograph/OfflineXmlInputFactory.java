package org.biograph;

import com.ctc.wstx.stax.WstxInputFactory;
import javax.xml.stream.XMLInputFactory;
import javax.xml.stream.XMLStreamException;
import java.util.ArrayList;
import java.util.List;

/** Standard StAX security properties applied to JAMI's declared Woodstox provider. */
public final class OfflineXmlInputFactory extends WstxInputFactory {
    private static final List<String> RESOLVER_ATTEMPTS = new ArrayList<>();

    public static synchronized List<String> resolverAttempts() {
        return new ArrayList<>(RESOLVER_ATTEMPTS);
    }

    private static synchronized void recordAttempt(String systemID) {
        RESOLVER_ATTEMPTS.add(systemID);
    }

    public OfflineXmlInputFactory() {
        super();
        setProperty(XMLInputFactory.SUPPORT_DTD, Boolean.FALSE);
        setProperty(XMLInputFactory.IS_SUPPORTING_EXTERNAL_ENTITIES, Boolean.FALSE);
        setXMLResolver((publicID, systemID, baseURI, namespace) -> {
            recordAttempt(systemID);
            throw new XMLStreamException("External XML resource resolution is disabled: " + systemID);
        });
    }
}
