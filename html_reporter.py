from typing import List, Dict
import os


class HTMLReporter:
    @staticmethod
    def write_html_report(
        metrics: List[Dict],
        output_path: str,
        title: str = "LLM Evaluation Report",
    ) -> None:
        """
        Write aggregated evaluation metrics to an HTML report.
        """

        rows = ""
        for row in metrics:
            rows += f"""
            <tr>
                <td>{row.get('model', '-')}</td>
                <td>{row.get('total_runs', '-')}</td>
                <td>{HTMLReporter._fmt(row.get('avg_quality'), 3)}</td>
                <td>{HTMLReporter._fmt(row.get('avg_cost'), 4)}</td>
                <td>{HTMLReporter._fmt(row.get('avg_latency'), 2)}</td>
            </tr>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{title}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    padding: 24px;
                }}
                h1 {{
                    margin-bottom: 16px;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 10px;
                    text-align: left;
                }}
                th {{
                    background-color: #f4f4f4;
                }}
                tr:nth-child(even) {{
                    background-color: #fafafa;
                }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            <table>
                <thead>
                    <tr>
                        <th>Model</th>
                        <th>Total Traces</th>
                        <th>Avg Quality</th>
                        <th>Avg Cost</th>
                        <th>Avg Latency (ms)</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </body>
        </html>
        """

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"[HTMLReporter] Report written to {output_path}")

    @staticmethod
    def _fmt(value, precision: int):
        if value is None:
            return "-"
        return round(value, precision)
