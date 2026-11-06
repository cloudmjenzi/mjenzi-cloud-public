---
title: How much GPU do you need to run an LLM?
date: 2026-11-06
summary: A practical rule of thumb for sizing GPU memory for large language models, with worked examples from 8B to 405B parameters.
author: Mjenzi Cloud team
tags: AI, GPU, Engineering
---

The first question in almost every AI infrastructure project is "which GPUs, and how many?" The answer depends mostly on one number: **GPU memory (VRAM)**. If the model and its working data don't fit, it won't run, or it will run painfully slowly.

Here is the rule of thumb our engineers use.

## Step 1: memory for the model weights

Multiply the number of parameters by the bytes used for each one:

| Precision | Bytes per parameter | 8B model | 70B model | 405B model |
|---|---|---|---|---|
| FP16 / BF16 | 2 | 16 GB | 140 GB | 810 GB |
| FP8 / INT8 | 1 | 8 GB | 70 GB | 405 GB |
| 4-bit (e.g. AWQ, GPTQ) | about 0.5 | 4–5 GB | 35–40 GB | about 200 GB |

Lower precision saves memory and usually speeds things up. For most business uses, a well-made FP8 or 4-bit version of a model gives answers very close to the original.

## Step 2: memory for the KV cache

While generating text, the model stores attention data for every token in the conversation. This is the **KV cache**, and it grows with context length and the number of users served at once.

For each token, the KV cache needs roughly:

```
2 × layers × KV heads × head size × bytes per value
```

For a 70B model like Llama 3 70B (80 layers, 8 KV heads, head size 128) at FP16, that is about **0.33 MB per token**. So:

- one user with a 32,000-token context needs about **10 GB**
- 20 users with 8,000-token contexts each need about **52 GB**

The KV cache is why a model that "fits" on paper can still run out of memory in production.

## Step 3: add headroom

Add about **10–20%** for the inference engine, activations and memory fragmentation. Engines such as vLLM reserve memory up front, so plan for the total.

## Worked examples

| Workload | Approximate memory | Good fit on Mjenzi Cloud |
|---|---|---|
| 8B model, FP16, internal chatbot | about 25 GB | 1× L40S (48 GB) |
| 70B model, 4-bit, small team | about 60 GB | 1× RTX PRO 6000 (96 GB) |
| 70B model, FP8, 20 concurrent users | about 140 GB | 2× H100 (188 GB) |
| 70B model, FP16, high throughput | about 220 GB | 2× H200 |
| 405B model, FP8 | about 500 GB | 4× H200 |

These are starting points. Real throughput also depends on GPU speed, memory bandwidth, the inference engine, batch sizes and how long your prompts and answers are.

## What about training and fine-tuning?

Training needs far more memory than inference. Full fine-tuning with the common Adam optimiser and mixed precision needs about **16 bytes per parameter** before activations, so more than 1 TB for a 70B model. That means a multi-GPU cluster with a fast interconnect such as InfiniBand.

Parameter-efficient methods such as **LoRA** and **QLoRA** only train a small set of extra weights. They can fine-tune a 70B model on one or two large GPUs, which is why they are the usual choice for adapting models to your own data.

## Try it with your own numbers

Our [Server Sizing Configurator](/sizing.html) does this maths for you. Choose a model size, precision, context length and number of users, and it estimates the GPU memory and recommends GPU servers, with a spec sheet you can download. When you're ready to run it, you can rent the same GPUs on [Mjenzi Cloud](/platform.html) in Nairobi, Johannesburg or Sydney.
