"""Versioned JSON catalog adapter."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


class JsonProblemTypeCatalog:
	def __init__(self, path: Path | None = None) -> None:
		catalog_path = path or Path(__file__).with_name("problem_types.json")
		with catalog_path.open(encoding="utf-8") as catalog_file:
			self._problem_types: dict[str, dict[str, Any]] = {
				problem_type["id"]: problem_type
				for problem_type in json.load(catalog_file)["problem_types"]
			}

	def list_problem_types(self) -> list[dict[str, Any]]:
		return [
			{"id": problem_type["id"], "name": problem_type["name"], "version": problem_type["version"]}
			for problem_type in self._problem_types.values()
		]

	def get_problem_type(self, problem_type_id: str) -> dict[str, Any] | None:
		problem_type = self._problem_types.get(problem_type_id)
		return deepcopy(problem_type) if problem_type is not None else None
