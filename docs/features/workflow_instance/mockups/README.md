# Mockup — WORKFLOW_INSTANCE

Protótipo estático e interativo para o fluxo de criação, pré-análise, otimização assíncrona e análise dos resultados.

Abra `index.html` diretamente ou execute um servidor local a partir desta pasta:

```bash
python3 -m http.server 8080
```

Então acesse `http://localhost:8080`.

O dashboard começa com uma instância TSP demonstrativa. Use **Nova Instância** para percorrer o assistente; os arquivos de exemplo permitem concluir sem selecionar arquivos reais. No grafo prévio, altere **Vizinhos mais próximos por cidade** para filtrar os arcos pelo menor tempo; o padrão é 20 e o limite efetivo é o número de cidades menos uma. Na tela de análise, **Otimizar** inicia uma simulação local, **Cancelar otimização** cancela essa simulação e **Visualizar resultados** aparece após a conclusão simulada. Na tabela de resultados, **Ver solução** mostra somente os arcos da rota escolhida e **Baixar resultado** exporta a sequência de cidades em CSV, incluindo o retorno à origem. Os mesmos pontos A–F são usados no grafo de entrada e nos grafos de solução. A navegação lateral permite sair do dashboard e voltar enquanto a simulação está em andamento. O centro de notificações também é demonstrativo.

Dados de gráfico, matrizes, soluções, execução e notificações são fictícios. Arquivos selecionados não são enviados nem interpretados; não há conexão com API ou solver.
