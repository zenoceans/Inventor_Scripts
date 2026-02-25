"""Tests for inventor_api.traversal module."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from conftest import (
    make_mock_assembly_com,
    make_mock_com_document,
    make_mock_com_occurrence,
)

from inventor_api.document import AssemblyDocument
from inventor_api.traversal import walk_assembly
from inventor_api.types import DocumentType


class TestWalkAssembly:
    def test_empty_assembly(self):
        asm_com = make_mock_assembly_com(occurrences=[])
        asm = AssemblyDocument(asm_com)
        result = walk_assembly(asm)
        # Should contain just the top-level assembly
        assert len(result) == 1
        assert result[0].is_top_level is True
        assert result[0].document.display_name == "Assembly"

    def test_flat_assembly_with_parts(self):
        part1 = make_mock_com_document(full_filename=r"C:\Projects\Part1.ipt", revision="A")
        part2 = make_mock_com_document(full_filename=r"C:\Projects\Part2.ipt", revision="B")
        occ1 = make_mock_com_occurrence(document=part1)
        occ2 = make_mock_com_occurrence(document=part2)
        asm_com = make_mock_assembly_com(occurrences=[occ1, occ2])
        asm = AssemblyDocument(asm_com)

        result = walk_assembly(asm)
        assert len(result) == 3  # top-level + 2 parts
        names = [c.document.display_name for c in result]
        assert "Assembly" in names
        assert "Part1" in names
        assert "Part2" in names

    def test_deduplicates_same_part(self):
        part = make_mock_com_document(full_filename=r"C:\Projects\Bolt.ipt")
        occ1 = make_mock_com_occurrence(document=part)
        occ2 = make_mock_com_occurrence(document=part)
        asm_com = make_mock_assembly_com(occurrences=[occ1, occ2])
        asm = AssemblyDocument(asm_com)

        result = walk_assembly(asm)
        # top-level + 1 unique part (not 2)
        assert len(result) == 2

    def test_filters_content_center(self):
        regular = make_mock_com_document(full_filename=r"C:\Projects\Bracket.ipt")
        cc_part = make_mock_com_document(
            full_filename=r"C:\Content Center Files\Fasteners\bolt.ipt"
        )
        occ1 = make_mock_com_occurrence(document=regular)
        occ2 = make_mock_com_occurrence(document=cc_part)
        asm_com = make_mock_assembly_com(occurrences=[occ1, occ2])
        asm = AssemblyDocument(asm_com)

        result = walk_assembly(asm, include_content_center=False)
        names = [c.document.display_name for c in result]
        assert "Bracket" in names
        assert "bolt" not in names

    def test_includes_content_center_when_flag_set(self):
        cc_part = make_mock_com_document(full_filename=r"C:\Content Center Files\bolt.ipt")
        occ = make_mock_com_occurrence(document=cc_part)
        asm_com = make_mock_assembly_com(occurrences=[occ])
        asm = AssemblyDocument(asm_com)

        result = walk_assembly(asm, include_content_center=True)
        names = [c.document.display_name for c in result]
        assert "bolt" in names

    def test_skips_suppressed_by_default(self):
        part = make_mock_com_document(full_filename=r"C:\Projects\Old.ipt")
        occ = make_mock_com_occurrence(document=part, suppressed=True)
        asm_com = make_mock_assembly_com(occurrences=[occ])
        asm = AssemblyDocument(asm_com)

        result = walk_assembly(asm, include_suppressed=False)
        assert len(result) == 1  # Only top-level

    def test_includes_suppressed_when_flag_set(self):
        part = make_mock_com_document(full_filename=r"C:\Projects\Old.ipt")
        occ = make_mock_com_occurrence(document=part, suppressed=True)
        asm_com = make_mock_assembly_com(occurrences=[occ])
        asm = AssemblyDocument(asm_com)

        result = walk_assembly(asm, include_suppressed=True)
        assert len(result) == 2
        suppressed_items = [c for c in result if c.is_suppressed]
        assert len(suppressed_items) == 1

    def test_nested_sub_assembly(self):
        # Build: TopAsm -> SubAsm -> Part
        part = make_mock_com_document(full_filename=r"C:\Projects\DeepPart.ipt")
        part_occ = make_mock_com_occurrence(document=part)
        sub_asm_com = make_mock_assembly_com(
            full_filename=r"C:\Projects\SubAsm.iam",
            occurrences=[part_occ],
        )
        sub_occ = make_mock_com_occurrence(document=sub_asm_com, doc_type=DocumentType.ASSEMBLY)
        top_asm_com = make_mock_assembly_com(
            full_filename=r"C:\Projects\TopAsm.iam",
            occurrences=[sub_occ],
        )
        top = AssemblyDocument(top_asm_com)

        result = walk_assembly(top)
        names = [c.document.display_name for c in result]
        assert "TopAsm" in names
        assert "SubAsm" in names
        assert "DeepPart" in names
        assert len(result) == 3

    def test_diamond_shared_part(self):
        # TopAsm -> SubA -> SharedPart
        #        -> SubB -> SharedPart (same file)
        shared = make_mock_com_document(full_filename=r"C:\Projects\Shared.ipt")
        shared_occ_a = make_mock_com_occurrence(document=shared)
        shared_occ_b = make_mock_com_occurrence(document=shared)

        sub_a = make_mock_assembly_com(
            full_filename=r"C:\Projects\SubA.iam", occurrences=[shared_occ_a]
        )
        sub_b = make_mock_assembly_com(
            full_filename=r"C:\Projects\SubB.iam", occurrences=[shared_occ_b]
        )
        occ_a = make_mock_com_occurrence(document=sub_a, doc_type=DocumentType.ASSEMBLY)
        occ_b = make_mock_com_occurrence(document=sub_b, doc_type=DocumentType.ASSEMBLY)
        top_com = make_mock_assembly_com(
            full_filename=r"C:\Projects\Top.iam", occurrences=[occ_a, occ_b]
        )
        top = AssemblyDocument(top_com)

        result = walk_assembly(top)
        names = [c.document.display_name for c in result]
        # Shared should appear only once
        assert names.count("Shared") == 1
        assert len(result) == 4  # Top + SubA + SubB + Shared

    def test_top_level_is_first(self):
        part = make_mock_com_document(full_filename=r"C:\Projects\P.ipt")
        occ = make_mock_com_occurrence(document=part)
        asm_com = make_mock_assembly_com(occurrences=[occ])
        asm = AssemblyDocument(asm_com)

        result = walk_assembly(asm)
        assert result[0].is_top_level is True
        assert result[1].is_top_level is False
