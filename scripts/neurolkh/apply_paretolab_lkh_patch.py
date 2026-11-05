#!/usr/bin/env python3
"""Apply the ParetoLab explicit-cost adaptation to a NeuroLKH checkout.

The upstream SWIG entry point only consumes coordinates and then optimizes
Euclidean distances. This patch keeps that coordinate path for feature
generation and, on the solve call, replaces the cost matrix with the integer
matrix packed at the tail of the parameter vector. It also copies the best
tour back into that vector, because the published wrapper only writes trial
costs. Candidate edges store C(), the explicit cost without node penalties;
D() adds Pi and makes the Lin-Kernighan gain fail its Precision assertion.
Graphs with fewer than 20 nodes repeat their nearest neighbor so
``featureGenerate`` can still fill the fixed 20-slot tensor the network expects.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


FEATURE_LOOP = """    /* ParetoLab: the network input is always 20 slots. ReadProblem clamps
       MaxCandidates to Dimension - 1, so small instances must repeat neighbors. */
    {
	int slots = 20;
	for (int i = 1; i <= n_nodes; i += 1) {
	    NN = NodeSet[i].CandidateSet;
	    int have_last = 0;
	    double last_index = 0;
	    double last_dist = 0;
	    double last_inverse = -1;
	    for (int j = 0; j < slots; j += 1) {
		if (NN && NN->To) {
		    invec[(i - 1) * slots + j] = (double) (NN->To->Id - 1);
		    invec[n_nodes * slots + (i - 1) * slots + j] = D(&NodeSet[i], NN->To);
		    int Top = 0;
		    Node *NTo = &NodeSet[NN->To->Id];
		    Candidate *ToCandidateSet = NTo->CandidateSet;
		    for (int l = 0; l < slots; l += 1) {
			if (!ToCandidateSet || !ToCandidateSet->To)
			    break;
			if (ToCandidateSet->To->Id == i) {
			    invec[n_nodes * slots * 2 + (i - 1) * slots + j] = (double) ((NN->To->Id - 1) * slots + l);
			    Top = 1;
			    break;
			}
			ToCandidateSet += 1;
		    }
		    if (Top == 0)
			invec[n_nodes * slots * 2 + (i - 1) * slots + j] = (double) -1;
		    last_index = invec[(i - 1) * slots + j];
		    last_dist = invec[n_nodes * slots + (i - 1) * slots + j];
		    last_inverse = invec[n_nodes * slots * 2 + (i - 1) * slots + j];
		    have_last = 1;
		    NN += 1;
		} else if (have_last) {
		    invec[(i - 1) * slots + j] = last_index;
		    invec[n_nodes * slots + (i - 1) * slots + j] = last_dist;
		    invec[n_nodes * slots * 2 + (i - 1) * slots + j] = last_inverse;
		} else {
		    invec[(i - 1) * slots + j] = 0;
		    invec[n_nodes * slots + (i - 1) * slots + j] = 0;
		    invec[n_nodes * slots * 2 + (i - 1) * slots + j] = -1;
		}
	    }
	}
    }
"""

HEADER_DECL = """int GettingNodeDegree;
extern int ParetoLabExplicitCosts;
void ParetoLabInstallExplicitCosts(double *invec, int length, int num_nodes);
void ParetoLabWriteTour(double *result, int length);
"""


def _replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"{path}: could not apply {label}")
    path.write_text(text.replace(old, new, 1))


def patch_feature_generate(path: Path) -> None:
    text = path.read_text()
    if "int slots = 20;" in text:
        return
    start = text.find("    for (int i = 1; i <= n_nodes; i += 1)")
    if start < 0:
        start = text.find("    /* ParetoLab: the network input is always 20 slots.")
    end = text.find("    return (int) ((GetTime() - StartTime) * 1000000);")
    if start < 0 or end < 0 or start > end:
        raise SystemExit(f"{path}: feature-generation loop not found")
    path.write_text(text[:start] + FEATURE_LOOP + text[end:])


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} NEUROLKH_ROOT")
    root = Path(sys.argv[1]).resolve()
    source = Path(__file__).resolve().parent / "ParetoLabExplicit.c"
    swig = root / "SRC_swig"
    shutil.copyfile(source, swig / "ParetoLabExplicit.c")

    _replace_once(
        swig / "INCLUDE" / "LKH.h",
        "int GettingNodeDegree;\n",
        HEADER_DECL,
        "header declaration",
    )
    _replace_once(
        swig / "LKHmain.c",
        "    ReadProblem(invec);\n",
        "    ReadProblem(invec);\n    ParetoLabInstallExplicitCosts(invec, n, num_nodes);\n",
        "explicit cost install",
    )
    _replace_once(
        swig / "LKHmain.c",
        "    return BestCost;\n",
        "    ParetoLabWriteTour(return_result, n);\n    return BestCost;\n",
        "tour export",
    )
    _replace_once(
        swig / "ReadCandidates.c",
        "\t    Id = (int) invec[n_nodes * 2 + i * 5 + j] + 1;\n"
        "\t    To = &NodeSet[Id];\n"
        "\t    Alpha = j * 100;\n"
        "\t    int tmp = SavedD[From->Id * n_nodes - n_nodes + To->Id - 1];\n"
        "\t    AddCandidate(From, To, tmp, Alpha);\n",
        "\t    Id = (int) invec[n_nodes * 2 + i * 5 + j] + 1;\n"
        "\t    if (Id < 1 || Id > Dimension)\n"
        "\t        continue;\n"
        "\t    To = &NodeSet[Id];\n"
        "\t    Alpha = j * 100;\n"
        "\t    int tmp = ParetoLabExplicitCosts ? C(From, To) :\n"
        "\t        SavedD[From->Id * n_nodes - n_nodes + To->Id - 1];\n"
        "\t    AddCandidate(From, To, tmp, Alpha);\n",
        "explicit candidate cost",
    )
    _replace_once(
        swig / "setup.py",
        "ARGS = ['-O3', '-Wall', '-IINCLUDE', '-DTWO_LEVEL_TREE', '-g']\n",
        "ARGS = ['-O3', '-Wall', '-IINCLUDE', '-DTWO_LEVEL_TREE', '-g', '-fcommon']\n",
        "gcc common symbols",
    )
    patch_feature_generate(swig / "FeatureGenerate.c")
    numpy_interface = (swig / "numpy.i").read_text()
    updated = (
        numpy_interface.replace("PyString_Check", "PyUnicode_Check")
        .replace("PyInt_Check", "PyLong_Check")
        .replace("PyInt_AsLong", "PyLong_AsLong")
    )
    if updated != numpy_interface:
        (swig / "numpy.i").write_text(updated)


if __name__ == "__main__":
    main()
