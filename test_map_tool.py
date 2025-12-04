#!/usr/bin/env python3
"""
Unit tests for map_tool.py

Tests the core functionality of the CLI tool without requiring network access.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import networkx as nx
import osmnx as ox

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from map_tool import (
    CUSTOM_FILTER,
    EXTRA_USEFUL_TAGS,
    PAVED_SURFACES,
    calculate_edge_length_km,
    configure_osmnx,
    create_parser,
    get_output_filepath,
    load_config,
    sanitize_place_name,
)


class TestSanitizePlaceName(unittest.TestCase):
    """Test place name sanitization."""

    def test_simple_name(self):
        """Test sanitization of a simple name."""
        result = sanitize_place_name("Vancouver")
        self.assertEqual(result, "Vancouver")

    def test_city_province(self):
        """Test sanitization of city, province format."""
        result = sanitize_place_name("Langley, British Columbia")
        self.assertEqual(result, "Langley_BC")

    def test_city_province_country(self):
        """Test sanitization of city, province, country format."""
        result = sanitize_place_name("Surrey, British Columbia, Canada")
        self.assertEqual(result, "Surrey_BC")

    def test_special_characters(self):
        """Test removal of special characters."""
        result = sanitize_place_name("New York, NY")
        self.assertNotIn(" ", result)
        self.assertNotIn(",", result)


class TestGetOutputFilepath(unittest.TestCase):
    """Test output filepath generation."""

    def test_with_custom_name(self):
        """Test with custom output name."""
        result = get_output_filepath(
            "Test Place",
            Path("/tmp/data"),
            output_name="custom.graphml",
        )
        self.assertEqual(result, Path("/tmp/data/custom.graphml"))

    def test_with_date(self):
        """Test with specified date."""
        result = get_output_filepath(
            "Langley, BC",
            Path("/tmp/data"),
            date="2024-01-15",
        )
        self.assertTrue(result.name.endswith("__20240115.graphml"))
        self.assertIn("Langley", result.name)

    def test_default_naming(self):
        """Test default naming convention."""
        result = get_output_filepath(
            "Vancouver, British Columbia",
            Path("/tmp/data"),
        )
        self.assertTrue(result.suffix == ".graphml")
        self.assertIn("Vancouver", result.name)


class TestConfigureOsmnx(unittest.TestCase):
    """Test OSMnx configuration."""

    def test_useful_tags_augmented(self):
        """Test that useful_tags_way is augmented with extra tags."""
        original_tags = list(ox.settings.useful_tags_way)
        configure_osmnx({}, timeout=60, memory=500000000)

        # Check that all extra tags are present
        current_tags = ox.settings.useful_tags_way
        for tag in EXTRA_USEFUL_TAGS:
            self.assertIn(tag, current_tags)

        # Restore original settings
        ox.settings.useful_tags_way = original_tags

    def test_timeout_override(self):
        """Test that timeout is properly set."""
        configure_osmnx({}, timeout=300)
        self.assertEqual(ox.settings.timeout, 300)

    def test_memory_override(self):
        """Test that memory is properly set."""
        configure_osmnx({}, memory=2000000000)
        self.assertEqual(ox.settings.memory, 2000000000)


class TestLoadConfig(unittest.TestCase):
    """Test configuration loading."""

    def test_default_config(self):
        """Test loading with no config file."""
        config = load_config(Path("/nonexistent/config.json"))
        self.assertIn("overpass_timeout", config)
        self.assertIn("overpass_memory", config)
        self.assertIn("data_root", config)

    def test_config_from_file(self):
        """Test loading from a config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"overpass_timeout": 999}, f)
            temp_path = Path(f.name)

        try:
            config = load_config(temp_path)
            self.assertEqual(config["overpass_timeout"], 999)
        finally:
            temp_path.unlink()


class TestCalculateEdgeLengthKm(unittest.TestCase):
    """Test edge length calculations."""

    def setUp(self):
        """Create a test graph."""
        self.graph = nx.MultiDiGraph()
        self.graph.add_node(1)
        self.graph.add_node(2)
        self.graph.add_node(3)
        # 1km edge
        self.graph.add_edge(1, 2, 0, highway="residential", surface="asphalt", length=1000.0)
        # 0.5km edge
        self.graph.add_edge(2, 3, 0, highway="track", surface="gravel", length=500.0)
        # 0.2km edge
        self.graph.add_edge(3, 1, 0, highway="service", service="alley", length=200.0)

    def test_total_length(self):
        """Test calculating total length."""
        total = calculate_edge_length_km(self.graph, lambda _: True)
        self.assertAlmostEqual(total, 1.7, places=1)

    def test_filter_by_highway(self):
        """Test filtering by highway type."""
        track_km = calculate_edge_length_km(
            self.graph, lambda d: d.get("highway") == "track"
        )
        self.assertAlmostEqual(track_km, 0.5, places=1)

    def test_filter_by_service(self):
        """Test filtering by service type."""
        alley_km = calculate_edge_length_km(
            self.graph, lambda d: d.get("service") == "alley"
        )
        self.assertAlmostEqual(alley_km, 0.2, places=1)


class TestConstants(unittest.TestCase):
    """Test constant definitions."""

    def test_extra_useful_tags_non_empty(self):
        """Test that extra useful tags list is populated."""
        self.assertGreater(len(EXTRA_USEFUL_TAGS), 20)
        self.assertIn("highway", EXTRA_USEFUL_TAGS)
        self.assertIn("surface", EXTRA_USEFUL_TAGS)
        self.assertIn("tracktype", EXTRA_USEFUL_TAGS)

    def test_custom_filter_valid(self):
        """Test that custom filter is a valid string."""
        self.assertIn("highway", CUSTOM_FILTER)
        self.assertIn("motorway", CUSTOM_FILTER)
        self.assertIn("track", CUSTOM_FILTER)
        self.assertIn("service", CUSTOM_FILTER)

    def test_paved_surfaces(self):
        """Test paved surfaces set."""
        self.assertIn("asphalt", PAVED_SURFACES)
        self.assertIn("concrete", PAVED_SURFACES)
        self.assertIn("paved", PAVED_SURFACES)
        self.assertNotIn("gravel", PAVED_SURFACES)
        self.assertNotIn("dirt", PAVED_SURFACES)


class TestCLIParser(unittest.TestCase):
    """Test CLI argument parsing."""

    def setUp(self):
        """Create parser."""
        self.parser = create_parser()

    def test_fetch_command(self):
        """Test parsing fetch command."""
        args = self.parser.parse_args([
            "fetch", "Test Place", "--output-dir", "/tmp/data"
        ])
        self.assertEqual(args.command, "fetch")
        self.assertEqual(args.place_name, "Test Place")
        self.assertEqual(args.output_dir, Path("/tmp/data"))

    def test_fetch_with_options(self):
        """Test fetch command with all options."""
        args = self.parser.parse_args([
            "fetch", "Test Place",
            "--output-dir", "/tmp/data",
            "--output-name", "custom.graphml",
            "--date", "2024-01-15",
            "--timeout", "300",
            "--retry", "5",
        ])
        self.assertEqual(args.output_name, "custom.graphml")
        self.assertEqual(args.date, "2024-01-15")
        self.assertEqual(args.timeout, 300)
        self.assertEqual(args.retry, 5)

    def test_merge_command(self):
        """Test parsing merge command."""
        args = self.parser.parse_args([
            "merge", "--folder", "/tmp/input", "--output", "/tmp/output.graphml"
        ])
        self.assertEqual(args.command, "merge")
        self.assertEqual(args.folder, Path("/tmp/input"))
        self.assertEqual(args.output, Path("/tmp/output.graphml"))

    def test_stats_command(self):
        """Test parsing stats command."""
        args = self.parser.parse_args(["stats", "/tmp/network.graphml"])
        self.assertEqual(args.command, "stats")
        self.assertEqual(args.filepath, Path("/tmp/network.graphml"))

    def test_verbose_flag(self):
        """Test verbose flag."""
        args = self.parser.parse_args(["-v", "stats", "/tmp/network.graphml"])
        self.assertTrue(args.verbose)


if __name__ == "__main__":
    unittest.main()
