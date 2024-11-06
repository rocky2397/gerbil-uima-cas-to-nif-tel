import os
import cassis
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD, NamespaceManager
from urllib.parse import quote

# Define NIF and ITSRDF Namespaces
NIF = Namespace('http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#')
ITSRDF = Namespace('http://www.w3.org/2005/11/its/rdf#')

def cas_to_nif_graph(cas_data, document_url, graph):
    # Retrieve the document text
    text = cas_data.sofa_string
    text_length = len(text.strip())  # Remove leading/trailing whitespace
    
    if text_length == 0:
        print(f"Warning: Document {document_url} has empty text.")
        return

    # Ensure text is properly escaped
    text_literal = Literal(text, lang='en')

    # Create the URI for the full text context
    context_uri = URIRef(f'{document_url}#char=0,{text_length}')

    # Add the context to the graph
    graph.add((context_uri, RDF.type, NIF.RFC5147String))
    graph.add((context_uri, RDF.type, NIF.String))
    graph.add((context_uri, RDF.type, NIF.Context))
    graph.add((context_uri, NIF.beginIndex, Literal(0, datatype=XSD.nonNegativeInteger)))
    graph.add((context_uri, NIF.endIndex, Literal(text_length, datatype=XSD.nonNegativeInteger)))
    graph.add((context_uri, NIF.isString, text_literal))

    # Extract entity annotations
    annotations_found = False
    for annotation in cas_data.select_all():
        if hasattr(annotation, 'begin') and hasattr(annotation, 'end'):
            begin = annotation.begin
            end = annotation.end

            if begin >= end or end > len(text):
                print(f"Warning: Invalid annotation positions in {document_url}: begin={begin}, end={end}")
                continue

            entity_text = text[begin:end].strip()
            if not entity_text:
                print(f"Warning: Empty entity text in {document_url} at positions {begin}-{end}.")
                continue

            entity_text_literal = Literal(entity_text, lang='en')

            # Fetch the annotation-level URI(s) for the named entity
            uris = getattr(annotation, 'identifier', None)
            if uris is None:
                # No identifiers; skip this annotation for D2KB
                continue  # Skip to the next annotation
            else:
                # Handle both string and list cases
                if isinstance(uris, str):
                    uris = [uris]  # Convert to list
                # Look for Wikidata URI
                wikidata_uri = None
                for u in uris:
                    if 'wikidata.org/entity' in u:
                        wikidata_uri = u
                        break  # Use the first Wikidata URI
                if wikidata_uri:
                    uri = wikidata_uri
                else:
                    # No Wikidata URI; skip this annotation for D2KB
                    continue  # Skip to the next annotation

            # Create the URI for the entity
            entity_uri = URIRef(f'{document_url}#char={begin},{end}')

            # Add the entity to the graph
            graph.add((entity_uri, RDF.type, NIF.RFC5147String))
            graph.add((entity_uri, RDF.type, NIF.String))
            graph.add((entity_uri, NIF.anchorOf, entity_text_literal))
            graph.add((entity_uri, NIF.beginIndex, Literal(begin, datatype=XSD.nonNegativeInteger)))
            graph.add((entity_uri, NIF.endIndex, Literal(end, datatype=XSD.nonNegativeInteger)))
            graph.add((entity_uri, NIF.referenceContext, context_uri))

            # Add the Wikidata URI as itsrdf:taIdentRef
            try:
                uri_ref = URIRef(uri)
                graph.add((entity_uri, ITSRDF.taIdentRef, uri_ref))
            except Exception as e:
                print(f"Invalid URI '{uri}' in document {document_url}: {e}")
                continue

            annotations_found = True

    if not annotations_found:
        print(f"No annotations found in document {document_url}.")


def main():
    # Set input and output directories
    input_folder = '../data/inception_entity_linking_exports_fixed_20241115/'
    output_folder = '../converted_data/'

    # Print working directory and paths
    print("Current working directory:", os.getcwd())
    print("Input folder:", input_folder)
    print("Output folder:", output_folder)

    # Create the output directory if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print("Created output directory:", output_folder)
    else:
        print("Output directory already exists:", output_folder)

    # Initialize an RDF graph
    g = Graph()

    # Bind namespaces for readability (optional)
    namespace_manager = NamespaceManager(g)
    namespace_manager.bind('nif', NIF)
    namespace_manager.bind('itsrdf', ITSRDF)
    namespace_manager.bind('xsd', XSD)
    namespace_manager.bind('rdf', RDF)
    namespace_manager.bind('rdfs', RDFS)
    g.namespace_manager = namespace_manager

    # List files in input folder
    files = os.listdir(input_folder)
    print("Files in input folder:", files)

    # Process each file in the input folder
    for filename in files:
        if filename.endswith('.json'):
            input_path = os.path.join(input_folder, filename)
            print(f"Processing {filename}...")
            try:
                with open(input_path, 'rb') as f:
                    cas_data = cassis.load_cas_from_json(f)

                # Use the filename to generate a unique document URL
                document_url = f"http://example.org/{os.path.splitext(filename)[0]}"

                # Convert to NIF format and add to the graph
                cas_to_nif_graph(cas_data, document_url, g)
            except Exception as e:
                print(f"Error processing {filename}: {e}")
        else:
            print(f"Skipping {filename} (not a JSON file)")

    print("Number of triples in graph:", len(g))

    if len(g) == 0:
        print("Warning: No data was added to the graph. The output file will be empty.")

    # Serialize the graph to a NIF file (Turtle format)
    output_path = os.path.join(output_folder, 'corpus.ttl')
    print("Output will be saved to:", output_path)
    try:
        g.serialize(destination=output_path, format='turtle')
        print("NIF corpus successfully saved.")
    except Exception as e:
        print(f"Error saving NIF corpus: {e}")

if __name__ == "__main__":
    main()
