"""Small synthetic classifier for integration tests; not a bundled user model."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import joblib
from django.test import override_settings
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline


@contextmanager
def local_model_fixture():
    with TemporaryDirectory() as folder:
        root = Path(folder)
        model = make_pipeline(TfidfVectorizer(analyzer='char', ngram_range=(2, 3)),
                              LogisticRegression(random_state=42))
        model.fit(['thank you friend', 'nice useful video', 'stupid idiot', 'you are awful'], [0, 0, 1, 1])
        joblib.dump(model, root / 'classifier.joblib')
        with override_settings(PRIVATE_DATA=root):
            yield root, {'label_keys': ['NON_TOXIC', 'TOXIC']}
