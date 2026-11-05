import numpy as np
from scipy.spatial.distance import cdist, pdist
from src.workflow_instance.domain.layout import mds_layout


def test_mds_layout_preserves_relative_distances():
    pts = np.array([[0, 0], [3, 0], [3, 4], [0, 4], [1.5, 2]], dtype=float)
    D = cdist(pts, pts)

    layout = mds_layout(D.tolist(), size=200.0)

    assert layout.min() >= 0 and layout.max() <= 200
    # Mesma configuração a menos de escala: razão constante entre distâncias
    ratio = pdist(layout) / pdist(pts)
    assert np.allclose(ratio, ratio[0], rtol=1e-6)