import requests
import threading
import time
import statistics  

def teste_carga(url, num_requests, intervalo=0):
    """
    Envia múltiplos requests e calcula métricas de performance:
    - Latência Média
    - P95 (95º percentil)
    - Error Rate
    - Disponibilidade
    """
    
    # Armazenamento de resultados 
    latencias = []
    status_codes = []
    erros_conexao = 0
    
    # Lock para garantir que múltiplas threads não escrevam nas listas ao mesmo tempo
    data_lock = threading.Lock()

    print(f"--- Teste de Carga: {num_requests} requests para {url} ---")

    def enviar_request(thread_id):
        nonlocal erros_conexao
        
        start_time = time.perf_counter() 
        try:
            response = requests.get(url, timeout=2)
            duration = (time.perf_counter() - start_time) * 1000 # Converter para ms
            
            with data_lock:
                latencias.append(duration)
                status_codes.append(response.status_code)
                
   
        except Exception as e:
            with data_lock:
                erros_conexao += 1
            # print(f"Thread {thread_id}: Falha - {e}")
        
        if intervalo > 0:
            time.sleep(intervalo)
    
    threads = []
    start_test = time.time()

    # Disparar threads
    for i in range(num_requests):
        thread = threading.Thread(target=enviar_request, args=(i,))
        threads.append(thread)
        thread.start()
    
    # Aguardar todas as threads terminarem
    for thread in threads:
        thread.join()
        
    total_time = time.time() - start_test

    # --- PROCESSAMENTO DOS DADOS ---
    total_tentativas = len(latencias) + erros_conexao
    
    if total_tentativas == 0:
        print("Nenhum request foi realizado.")
        return

    # 1. Error Rate (Considerando Erros de Conexão + HTTP 5xx/4xx)
    # Aqui vamos considerar erro qualquer coisa que não seja 200-299 ou exceção
    erros_http = sum(1 for code in status_codes if not 200 <= code < 300)
    total_erros = erros_conexao + erros_http
    error_rate = (total_erros / total_tentativas) * 100

    # 2. Disponibilidade
    disponibilidade = 100 - error_rate

    # 3. Métricas de Latência
    if latencias:
        media_latencia = statistics.mean(latencias)
        # P95: 95% dos requests foram mais rápidos que este valor
        p95_latencia = statistics.quantiles(latencias, n=20)[18] # n=20 divide em 5%, o index 18 é 95%
        min_latencia = min(latencias)
        max_latencia = max(latencias)
    else:
        media_latencia = p95_latencia = min_latencia = max_latencia = 0

    # --- RELATÓRIO FINAL ---
    print("\n" + "="*40)
    print(f"RESUMO DO TESTE ({total_time:.2f}s totais)")
    print("="*40)
    print(f"Total Requests:      {total_tentativas}")
    print(f"Sucessos (2xx):      {len(latencias) - erros_http}")
    print(f"Erros (HTTP/Rede):   {total_erros}")
    print("-" * 40)
    print(f"Disponibilidade:     {disponibilidade:.2f}%")
    print(f"Error Rate:          {error_rate:.2f}%")
    print("-" * 40)
    if latencias:
        print(f"Latência Média:      {media_latencia:.2f} ms")
        print(f"Latência P95:        {p95_latencia:.2f} ms")
        print(f"Latência Min/Max:    {min_latencia:.2f} / {max_latencia:.2f} ms")
    print("="*40)

if __name__ == "__main__":

    URL_TESTE = "http://localhost:8080" 
    
    
    teste_carga(URL_TESTE, num_requests=10000, intervalo=0)