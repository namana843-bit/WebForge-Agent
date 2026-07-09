#!/usr/bin/env python3
"""Enhanced Data Exporter Plugin supporting CSV, JSON, Excel, schema validation, and scheduling."""

import os
import csv
import json
import time
import threading
from pathlib import Path
from plugin_interface import BrowserPlugin

class DataExporterPlugin(BrowserPlugin):
    """Plugin to export data in multiple formats with validation and scheduling."""

    def __init__(self, agent):
        self.agent = agent
        self.schedules = {}  # Keep track of active schedules: {id: threading.Event}

    def execute(self, action: str, **kwargs):
        try:
            if action == "export_data":
                data = kwargs.get("data")
                fmt = kwargs.get("format", "json").lower()
                schema = kwargs.get("schema")
                output_path = kwargs.get("output_path")
                
                # Parse inputs if passed as JSON string
                if isinstance(data, str):
                    data = json.loads(data)
                if isinstance(schema, str) and schema:
                    schema = json.loads(schema)
                    
                return self.export_data(data, fmt, schema, output_path)
                
            elif action == "schedule_export":
                interval = float(kwargs.get("interval", 60.0))
                data = kwargs.get("data")
                fmt = kwargs.get("format", "json").lower()
                schema = kwargs.get("schema")
                filename = kwargs.get("filename")
                
                if isinstance(data, str):
                    data = json.loads(data)
                if isinstance(schema, str) and schema:
                    schema = json.loads(schema)
                    
                return self.schedule_export(interval, data, fmt, schema, filename)
                
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": str(e)}

    def validate_schema(self, data_list, schema):
        """Validates that items in data_list match the keys and basic types of the schema."""
        if not schema:
            return data_list, []

        validated = []
        errors = []
        
        for idx, item in enumerate(data_list):
            new_item = {}
            item_errors = []
            
            for key, expected_type_str in schema.items():
                if key not in item:
                    item_errors.append(f"Missing key '{key}' at index {idx}")
                    continue
                
                val = item[key]
                # Validate & transform type if needed
                try:
                    if expected_type_str == "int":
                        new_item[key] = int(val)
                    elif expected_type_str == "float":
                        new_item[key] = float(val)
                    elif expected_type_str == "str":
                        new_item[key] = str(val)
                    elif expected_type_str == "bool":
                        new_item[key] = bool(val)
                    else:
                        new_item[key] = val
                except ValueError:
                    item_errors.append(f"Key '{key}' at index {idx} failed validation: cannot convert to {expected_type_str}")
                    
            if item_errors:
                errors.extend(item_errors)
            else:
                validated.append(new_item)
                
        return validated, errors

    def export_data(self, data, fmt, schema=None, output_path=None):
        """Validates and writes data to the specified format."""
        # Ensure data is a list of dicts
        if isinstance(data, dict):
            data_list = [data]
        elif isinstance(data, list):
            data_list = data
        else:
            return {"error": "Data must be a dictionary or a list of dictionaries"}

        # Validate against schema
        validated_data, errors = self.validate_schema(data_list, schema)
        if errors:
            print(f"[DataExporter] Schema validation warnings: {errors}")

        if not validated_data:
            return {"error": "No valid data to export after schema validation", "errors": errors}

        # Generate default path if none provided
        if not output_path:
            output_dir = Path("data/exports")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"export_{int(time.time())}.{fmt}"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(validated_data, f, indent=2)
                
        elif fmt == "csv":
            keys = validated_data[0].keys()
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(validated_data)
                
        elif fmt == "excel":
            try:
                import openpyxl
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Scraped Data"
                
                # Write header
                keys = list(validated_data[0].keys())
                ws.append(keys)
                
                # Write rows
                for row in validated_data:
                    ws.append([row.get(k) for k in keys])
                    
                wb.save(output_path)
            except ImportError:
                return {"error": "openpyxl library not installed. Cannot export to Excel."}
        else:
            return {"error": f"Unsupported format: {fmt}"}

        print(f"[DataExporter] Data successfully exported to {output_path}")
        return {"success": True, "path": str(output_path), "format": fmt, "record_count": len(validated_data)}

    def schedule_export(self, interval_seconds, data, fmt, schema=None, filename=None):
        """Starts a background thread to repeatedly export data at the specified interval."""
        schedule_id = f"sched_{int(time.time())}"
        stop_event = threading.Event()
        
        def run_schedule():
            step = 1
            while not stop_event.is_set():
                out_name = filename or f"scheduled_{schedule_id}_step{step}.{fmt}"
                output_dir = Path("data/exports/scheduled")
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / out_name
                
                print(f"\n[Scheduled Export {schedule_id}] Exporting step {step}...")
                self.export_data(data, fmt, schema, output_path)
                
                step += 1
                # Wait or check stop event
                for _ in range(int(interval_seconds)):
                    if stop_event.is_set():
                        break
                    time.sleep(1)
                    
        self.schedules[schedule_id] = stop_event
        t = threading.Thread(target=run_schedule, daemon=True)
        t.start()
        
        print(f"[DataExporter] Started scheduled export task ID: {schedule_id} (interval: {interval_seconds}s)")
        return {"success": True, "schedule_id": schedule_id, "interval": interval_seconds}
