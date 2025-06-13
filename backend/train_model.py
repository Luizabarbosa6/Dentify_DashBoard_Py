import pandas as pd
from pymongo import MongoClient
from xgboost import XGBClassifier
from sklearn.preprocessing import OneHotEncoder, LabelEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score
import pickle
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Conexão com MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client["meu_banco"]
colecao = db["meus_dados"]

# Buscar dados
dados = list(colecao.find({}, {"_id": 0}))

# Criar DataFrame
lista = []
for d in dados:
    lista.append({
        "idade": d.get("vitima", {}).get("idade"),
        "etnia": d.get("vitima", {}).get("etnia"),
        "localizacao": d.get("localizacao"),
        "tipo_do_caso": d.get("tipo_do_caso")
    })

df = pd.DataFrame(lista)

# Remover linhas com dados ausentes
df = df.dropna(subset=["idade", "etnia", "localizacao", "tipo_do_caso"])

# Separar variáveis
X = df[["idade", "etnia", "localizacao"]]
y = df["tipo_do_caso"]

# Codificar variável alvo
label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y)

# Pré-processamento
categorical_features = ["etnia", "localizacao"]
numeric_features = ["idade"]

preprocessor = ColumnTransformer([
    ("cat", OneHotEncoder(handle_unknown='ignore'), categorical_features),
    ("num", "passthrough", numeric_features)
])

# Pipeline de ML
pipeline = Pipeline([
    ("preprocessor", preprocessor),
    ("classifier", XGBClassifier(
        use_label_encoder=False,
        eval_metric="mlogloss",
        random_state=42
    ))
])

# Treinar modelo
pipeline.fit(X, y_encoded)

# Calcular acurácia do modelo
y_pred = pipeline.predict(X)
acc = accuracy_score(y_encoded, y_pred)

# Salvar modelo, label encoder e acurácia
with open("model.pkl", "wb") as f:
    pickle.dump({
        "pipeline": pipeline,
        "label_encoder": label_encoder,
        "accuracy": acc
    }, f)

print(f"✅ Modelo treinado com sucesso!")
print(f"📊 Acurácia no conjunto de treino: {acc:.4f}")
print("💾 Arquivo salvo como model.pkl")
