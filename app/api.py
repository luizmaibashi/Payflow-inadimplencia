from fastapi import FastAPI, HTTPException
from app.schemas import CreditRequest, CreditResponse
from app.service import CreditScoringService

app = FastAPI(
    title="PayFlow API - Risco de Crédito",
    description="API de predição de inadimplência baseada em Machine Learning (Random Forest).",
    version="1.0.0"
)

# Inicializando o serviço (Deep Module: esconde a complexidade de ML)
try:
    scoring_service = CreditScoringService()
except Exception as e:
    scoring_service = None
    print(f"Erro ao inicializar o serviço: {e}")

@app.get("/")
def health_check():
    return {"status": "ok", "message": "PayFlow API está rodando!"}

@app.post("/predict", response_model=CreditResponse)
def predict_risk(request: CreditRequest):
    if not scoring_service:
        raise HTTPException(status_code=500, detail="Modelo de ML não foi carregado corretamente no servidor.")
    
    try:
        probabilidade, decisao, comprometimento, msg = scoring_service.predict(request)
        
        return CreditResponse(
            probabilidade_inadimplencia=float(probabilidade),
            decisao_sugerida=decisao,
            comprometimento_renda_pct=float(comprometimento),
            mensagem_alerta=msg
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao processar predição: {str(e)}")
