#!/usr/bin/env python3
"""
Converts path.json and functions.json into AutoData.java
"""

import json
import sys
from pathlib import Path


def load_json_file(filepath):
    """Load and parse a JSON file."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{filepath}': {e}")
        sys.exit(1)


def generate_path_points(path_data):
    """Generate Java code for path points."""
    points = []
    for i, point in enumerate(path_data):
        points.append(f'        new Point({point["x"]}, {point["y"]})')
    return ',\n'.join(points)


def generate_functions(functions_data):
    """Generate Java code for functions."""
    func_entries = []
    for i, func in enumerate(functions_data):
        func_str = f'''        new FunctionData(
            "{func["name"]}",
            {func["x"]},
            {func["y"]},
            {func["rotation"]},
            FunctionType.{func["type"].upper()},
            ActionType.{func["action"].upper()}
        )'''
        func_entries.append(func_str)
    return ',\n'.join(func_entries)


def generate_templates(templates):
    """Generate Java code for templates array."""
    template_entries = [f'"{t}"' for t in templates]
    return ', '.join(template_entries)


def generate_auto_data_java(path_json, functions_json):
    """Generate the complete AutoData.java file content."""
    
    path_points = generate_path_points(path_json['path'])
    functions = generate_functions(functions_json['functions'])
    templates = generate_templates(functions_json['templates'])
    start_pos = functions_json['start_pos']
    
    java_content = f'''package org.firstinspires.ftc.teamcode.kool;
    
public class AutoData {{
    
    // Path points
    public static final Point[] PATH = {{
{path_points}
    }};
    
    // Start position
    public static final Position START_POS = new Position(
        {start_pos['x']},
        {start_pos['y']},
        {start_pos['rotation']}
    );
    
    // Functions
    public static final FunctionData[] FUNCTIONS = {{
{functions}
    }};
    
    // Templates
    public static final String[] TEMPLATES = {{ {templates} }};
    
    // Helper classes
    public static class Point {{
        public final double x;
        public final double y;
        
        public Point(double x, double y) {{
            this.x = x;
            this.y = y;
        }}
    }}
    
    public static class Position {{
        public final double x;
        public final double y;
        public final double rotation;
        
        public Position(double x, double y, double rotation) {{
            this.x = x;
            this.y = y;
            this.rotation = rotation;
        }}
    }}
    
    public static class FunctionData {{
        public final String name;
        public final double x;
        public final double y;
        public final double rotation;
        public final FunctionType type;
        public final ActionType action;
        
        public FunctionData(String name, double x, double y, double rotation,
                          FunctionType type, ActionType action) {{
            this.name = name;
            this.x = x;
            this.y = y;
            this.rotation = rotation;
            this.type = type;
            this.action = action;
        }}
    }}
    
    public enum FunctionType {{
        RUN_WHILE_MOVING,
        WAIT_TILL
    }}
    
    public enum ActionType {{
        FUNCTION
    }}
}}
'''
    
    return java_content


def main():
    """Main conversion function."""
    # File paths
    path_file = 'path.json'
    functions_file = 'functions.json'
    output_file = 'AutoData.java'
    
    # Load JSON files
    print(f"Loading {path_file}...")
    path_data = load_json_file(path_file)
    
    print(f"Loading {functions_file}...")
    functions_data = load_json_file(functions_file)
    
    # Generate Java code
    print("Generating AutoData.java...")
    java_code = generate_auto_data_java(path_data, functions_data)
    
    # Write to output file
    with open(output_file, 'w') as f:
        f.write(java_code)
    
    print(f"Successfully created {output_file}")


if __name__ == '__main__':
    main()