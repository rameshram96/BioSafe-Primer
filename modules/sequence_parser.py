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
