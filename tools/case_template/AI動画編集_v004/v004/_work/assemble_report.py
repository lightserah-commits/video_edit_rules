"""確認_v004.md を組み立てる（_work/report_head.md ＋ _work/report_tables.md〔report_tables.py の出力〕）。
  python3 v004/_work/report_tables.py > v004/_work/report_tables.md && python3 v004/_work/assemble_report.py"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
head = open(os.path.join(HERE, "report_head.md"), encoding="utf-8").read()
tables = open(os.path.join(HERE, "report_tables.md"), encoding="utf-8").read()
open(os.path.join(V, "確認_v004.md"), "w", encoding="utf-8").write(head.replace("<<TABLES>>", tables))
print("確認_v004.md", len(head) + len(tables), "字")
