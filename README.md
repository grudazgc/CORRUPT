# BRIBRRYBUSTER.XYZ (Corrupt.space)

Dokumentacja została podzielona na:

- `docs/ARCHITECTURE.md` — techniczna architektura MVP,
- `backend/` — szkic API i logiki reward,
- `frontend/` — szkic aplikacji React (preview nagrody),
- `programs/corrupt_reports/` — szkic programu Solana.

## Szybki start

### Backend

```bash
cd backend
npm install
npm run check
```

### Frontend

Podłącz komponent `frontend/src/App.jsx` do istniejącej konfiguracji React/Vite.

### Solana (scaffold)

Kod programu znajduje się w `programs/corrupt_reports/src/lib.rs` i zawiera model statusów oraz funkcję `calculate_reward`.
