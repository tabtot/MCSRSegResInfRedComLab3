import requests
import threading
import time
import subprocess
import matplotlib.pyplot as plt
from datetime import datetime
from collections import defaultdict

# --- CONFIGURAÇÕES ---
URL = "http://localhost:8080"
NUM_REQUESTS = 100000   # Volume suficiente para o teste
TIMEOUT = 2            

# --- ARMAZENAMENTO ---
timestamps_sucesso = []
timestamps_erro = []
dados_latencia = []   
dados_replicas = []   

start_time = 0
running = True

def obter_replicas():
    try:
        cmd = "kubectl get deployment demo-api -o jsonpath='{.status.readyReplicas}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        output = result.stdout.strip()
        if not output: return 0
        return int(output.replace("'", ""))
    except:
        return 1

def monitor_k8s():
    while running:
        tempo_atual = time.time() - start_time
        qtd = obter_replicas()
        dados_replicas.append((tempo_atual, qtd))
        time.sleep(0.5)

def enviar_request(thread_id):
    global timestamps_sucesso, timestamps_erro, dados_latencia
    
    try:
        inicio = time.time()
        resp = requests.get(URL, timeout=TIMEOUT)
        fim = time.time()
        
        tempo_relativo = fim - start_time
        duracao_ms = (fim - inicio) * 1000  
        
        if resp.status_code >= 400:
            timestamps_erro.append(tempo_relativo)
        else:
            timestamps_sucesso.append(tempo_relativo)
            dados_latencia.append((tempo_relativo, duracao_ms))
            
    except Exception:
        tempo_relativo = time.time() - start_time
        timestamps_erro.append(tempo_relativo)

def executar_teste():
    global start_time, running
    print(f"--- A INICIAR TESTE DE CARGA ({NUM_REQUESTS} reqs) ---")
    
    start_time = time.time()
    t_monitor = threading.Thread(target=monitor_k8s)
    t_monitor.start()
    
    threads = []
    for i in range(NUM_REQUESTS):
        t = threading.Thread(target=enviar_request, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    
    print("--- A aguardar estabilização (5s)... ---")
    time.sleep(5)
    running = False
    t_monitor.join()
    
    print("--- A GERAR GRÁFICOS (LATÊNCIA + THROUGHPUT + SCALING)... ---")
    gerar_graficos_completo()

def gerar_graficos_completo():
    bucket_sucesso = defaultdict(int)
    bucket_erro = defaultdict(int)
    
    max_tempo = 0
    
    for t in timestamps_sucesso:
        sec = int(t)
        bucket_sucesso[sec] += 1
        max_tempo = max(max_tempo, sec)
        
    for t in timestamps_erro:
        sec = int(t)
        bucket_erro[sec] += 1
        max_tempo = max(max_tempo, sec)
        
    if dados_replicas:
        max_tempo = max(max_tempo, max(t for t, _ in dados_replicas))

    eixo_x_throughput = range(int(max_tempo) + 1)
    y_sucesso = [bucket_sucesso[t] for t in eixo_x_throughput]
    y_erro = [bucket_erro[t] for t in eixo_x_throughput]

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 15), sharex=True)
    
   
    if dados_latencia:
        
        tempos, lats = zip(*sorted(dados_latencia))
        ax1.plot(tempos, lats, color='blue', alpha=0.5, linewidth=0.5, label='Latência (ms)')
        ax1.set_ylabel('Latência (ms)')
        ax1.set_title('1. Performance: Latência dos Pedidos')
        ax1.legend(loc="upper right")
        ax1.grid(True, alpha=0.3)
    else:
        ax1.text(0.5, 0.5, "Sem dados de latência (apenas erros?)", ha='center', transform=ax1.transAxes)

    
    ax2.plot(eixo_x_throughput, y_sucesso, color='blue', label='Sucessos (Req/s)', linewidth=2)
    ax2.plot(eixo_x_throughput, y_erro, color='red', label='Erros (Req/s)', linewidth=2, linestyle='--')
    ax2.set_title('2. Throughput: Sucesso vs Erros')
    ax2.set_ylabel('Pedidos por Segundo')
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.3)
    

    if dados_replicas:
        tempos_r, qtds = zip(*sorted(dados_replicas))
        ax3.step(tempos_r, qtds, where='post', color='green', linewidth=3, label='Réplicas Ativas')
        ax3.set_ylabel('Nº Pods')
        ax3.set_xlabel('Tempo (segundos)')
        ax3.set_title('3. Autoscaling (HPA)')
        ax3.set_ylim(bottom=0, top=12)
        ax3.legend(loc="lower right")
        ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    timestamp = datetime.now().strftime("%H%M%S")
    nome = f"relatorio_completo_{timestamp}.png"
    plt.savefig(nome)
    print(f"Gráfico guardado com sucesso: {nome}")
    plt.show()

if __name__ == "__main__":
    executar_teste()