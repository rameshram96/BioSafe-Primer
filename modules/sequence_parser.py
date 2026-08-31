from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature
import io

def parse_sequence(file_content, file_format):
    """
    Parse FASTA or GenBank sequence file.
    Returns: dict with sequence, name, length, features
    """
    try:
        handle = io.StringIO(file_content)
        record = next(SeqIO.parse(handle, file_format))

        features = []
        if file_format == 'genbank':
            for feat in record.features:
                if feat.type not in ['source']:
                    label = feat.qualifiers.get('gene',
                            feat.qualifiers.get('product',
                            feat.qualifiers.get('label', [feat.type])))[0]
                    features.append({
                        'type': feat.type,
                        'label': label,
                        'start': int(feat.location.start),
                        'end': int(feat.location.end),
                        'strand': feat.location.strand
                    })

        return {
            'name': record.id,
            'description': record.description,
            'sequence': str(record.seq).upper(),
            'length': len(record.seq),
            'features': features
        }
    except Exception as e:
        raise ValueError(f"Error parsing sequence: {str(e)}")

def detect_format(filename):
    """Detect file format from extension."""
    filename = filename.lower()
    if filename.endswith(('.gb', '.gbk', '.genbank')):
        return 'genbank'
    elif filename.endswith(('.fa', '.fasta', '.fna')):
        return 'fasta'
    else:
        return 'fasta'


def parse_pasted_sequence(text, seq_name="Pasted_Sequence"):
    """
    Parse sequence pasted directly into a text box.
    Accepts three kinds of pasted content:
      1. FASTA text (starts with '>')
      2. GenBank text (starts with 'LOCUS')
      3. Raw sequence with no header (letters only, or letters mixed with
         whitespace/numbers e.g. copied from a numbered text file) — this is
         wrapped into a minimal FASTA record using `seq_name`.
    Returns the same dict shape as parse_sequence().
    """
    if text is None:
        raise ValueError("No sequence text provided.")
    text = text.strip()
    if not text:
        raise ValueError("Pasted sequence is empty.")

    stripped_upper = text.upper()
    if stripped_upper.startswith('LOCUS'):
        return parse_sequence(text, 'genbank')

    if text.startswith('>'):
        return parse_sequence(text, 'fasta')

    # Raw / plain sequence: keep only letters (drops line numbers, spaces,
    # accidental digits, and stray whitespace that often come from copy-paste).
    cleaned = ''.join(ch for ch in text if ch.isalpha())
    if not cleaned:
        raise ValueError(
            "No valid sequence characters found in the pasted text. "
            "Paste a FASTA record (starting with '>'), a GenBank record "
            "(starting with 'LOCUS'), or the raw sequence letters."
        )
    name = (seq_name or "Pasted_Sequence").strip().replace(' ', '_') or "Pasted_Sequence"
    fasta_text = f">{name}\n{cleaned}\n"
    return parse_sequence(fasta_text, 'fasta')
