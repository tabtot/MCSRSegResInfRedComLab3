import requests
import threading
import time
import subprocess
import matplotlib.pyplot as plt
import json
from datetime import datetime

# --- CONFIGURAÇÕES ---
URL = "http://localhost:8080"
NUM_REQUESTS = 50000  
INTERVALO = 0         # 0 = Ataque contínuo (DoS)
TIMEOUT = 2           # Segundos até considerar timeout

# --- ARMAZENAMENTO DE DADOS ---
dados_latencia = []   # (tempo_relativo, latencia_ms)
dados_erros = []      # (tempo_relativo, 1) - Apenas marca o instante do erro
dados_replicas = []   # (tempo_relativo, num_replicas)

start_time = 0
running = True

def obter_replicas():
    """Consulta o Kubernetes para saber quantos pods estão prontos."""
    try:
        # Comando para obter o número de réplicas prontas em JSON
        cmd = "kubectl get deployment demo-api -o jsonpath='{.status.readyReplicas}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        output = result.stdout.strip()
        if not output: return 0
        return int(output.replace("'", ""))
    except:
        return 1 # Assume 1 se der erro de leitura

def monitor_k8s():
    """Thread que regista o número de réplicas a cada 0.5 segundos."""
    while running:
        tempo_atual = time.time() - start_time
        qtd = obter_replicas()
        dados_replicas.append((tempo_atual, qtd))
        time.sleep(0.5)

def enviar_request(thread_id):
    """Envia um request e regista o resultado."""
    global dados_latencia, dados_erros
    
    try:
        inicio = time.time()
        resp = requests.get(URL, timeout=TIMEOUT)
        fim = time.time()
        
        tempo_relativo = fim - start_time
        duracao_ms = (fim - inicio) * 1000
        
        # Se o status não for 200 (ex: 503 do Rate Limit), conta como 'Erro' para o gráfico
        if resp.status_code >= 400:
            dados_erros.append((tempo_relativo, 1))
        else:
            dados_latencia.append((tempo_relativo, duracao_ms))
            
    except Exception:
        # Erro de conexão ou Timeout
        tempo_relativo = time.time() - start_time
        dados_erros.append((tempo_relativo, 1))

def executar_teste():
    global start_time, running
    print(f"--- INICIANDO TESTE COMPLETO ({NUM_REQUESTS} requests) ---")
    print("1. Monitorização de réplicas: ATIVA")
    print("2. Ataque HTTP: A INICIAR...")
    
    start_time = time.time()
    
    # Inicia monitorização do HPA em background
    t_monitor = threading.Thread(target=monitor_k8s)
    t_monitor.start()
    
    # Inicia o ataque
    threads = []
    for i in range(NUM_REQUESTS):
        t = threading.Thread(target=enviar_request, args=(i,))
        threads.append(t)
        t.start()
        # Pequena pausa para não bloquear o CPU do script Python
        # if i % 100 == 0: time.sleep(0.01)

    # Aguarda o fim dos requests
    for t in threads:
        t.join()
    
    # Dá mais 5 segundos para registar a estabilização das réplicas
    print("--- Ataque terminado. A aguardar estabilização (5s)... ---")
    time.sleep(5)
    
    running = False
    t_monitor.join()
    print("--- DADOS RECOLHIDOS. A GERAR GRÁFICOS... ---")
    gerar_graficos()

def gerar_graficos():
    # Configura 3 gráficos empilhados
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
    
    # 1. Latência
    if dados_latencia:
        tempos, lats = zip(*sorted(dados_latencia))
        ax1.plot(tempos, lats, color='blue', alpha=0.6, linewidth=0.5, label='Latência (ms)')
        ax1.set_ylabel('Latência (ms)')
        ax1.set_title('Impacto do Ataque: Latência')
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)

    # 2. Error Rate (Visualização de densidade)
    if dados_erros:
        tempos_e, _ = zip(*sorted(dados_erros))
        # Criar um histograma de erros por segundo seria ideal, mas scatter serve para visualizar "manchas" de erro
        ax2.scatter(tempos_e, [1]*len(tempos_e), color='red', s=1, alpha=0.5, label='Erros (503/Timeout)')
        ax2.set_ylabel('Ocorrência de Erros')
        ax2.set_title('Distribuição de Erros (Rate Limiting)')
        ax2.set_yticks([]) # Remove números do eixo Y
        ax2.legend(loc='upper right')
        ax2.grid(True, alpha=0.3)
    else:
        ax2.text(0.9, 0.5, "Sem Erros Registados", ha='center')

    # 3. Réplicas (HPA)
    if dados_replicas:
        tempos_r, qtds = zip(*sorted(dados_replicas))
        ax3.step(tempos_r, qtds, where='post', color='green', linewidth=2, label='Réplicas Ativas')
        ax3.set_ylabel('Nº Pods')
        ax3.set_xlabel('Tempo (segundos)')
        ax3.set_title('Autoscaling (HPA)')
        ax3.set_ylim(bottom=0, top=12) # Margem até 12 já que o max é 10
        ax3.legend(loc='upper right')
        ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    timestamp = datetime.now().strftime("%H%M%S")
    nome_ficheiro = f"relatorio_final_{timestamp}.png"
    plt.savefig(nome_ficheiro)
    print(f" Gráfico guardado com sucesso: {nome_ficheiro}")
    plt.show() # Tenta abrir a janela

if __name__ == "__main__":
    executar_teste()