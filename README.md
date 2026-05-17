---
Instructions on how to deploy the project
---
# 1. Clone
```
git clone https://github.com/your/graph-query
```

# 2. Backend
```
cd backend
pip install -r requirements.txt
python3 scripts/crawl_osm.py    # fetches OSM data → creates apartmentgps.db automatically
uvicorn main:app --reload --port 8000
```

No Docker, no MySQL, no .env needed — SQLite is built into Python.

# 3. Frontend
Open another terminal:
```
npm install --registry=[https://registry.npmjs.org/](https://registry.npmjs.org/)
npm run dev
👉 http://localhost:5173/
```
