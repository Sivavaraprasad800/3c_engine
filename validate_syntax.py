import ast
for f in ["server.py","face_engine.py","database.py","kloudspot_service.py"]:
    try:
        ast.parse(open(f,encoding="utf-8-sig").read())
        print(f"{f}: OK")
    except SyntaxError as e:
        print(f"{f}: SYNTAX ERROR - {e}")
