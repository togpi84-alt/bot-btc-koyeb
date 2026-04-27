import pandas as pd
import numpy as np
import asyncio
from telegram import Bot
from telegram.error import TelegramError
import time
import requests
import os


# Use variáveis de ambiente para segurança
TOKEN = os.environ.get('TELEGRAM_TOKEN', '8600645490:AAGsVpwuUhIbNXPujr-JkbMLQ1HH-SRUwLE')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '1743878749')


async def enviar_telegram(bot, mensagem):
    """Função assíncrona para enviar mensagem"""
    try:
        await bot.send_message(chat_id=CHAT_ID, text=mensagem)
        print(f"✅ Mensagem enviada!")
        return True
    except Exception as e:
        print(f"❌ Erro ao enviar: {e}")
        return False


def get_btc_price(limit=500):
    """Pega os últimos 500 candles"""
    try:
        url = f'https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit={limit}'
        data = requests.get(url, timeout=5).json()
        closes = [float(k[4]) for k in data]
        return closes
    except Exception as e:
        print(f"❌ Erro ao obter dados Binance: {e}")
        return None


def calculate_stoch_rsi_correct(prices, periodo_ifr=14, periodo_estocastico=14, suave_k=3, suave_d=3):
    """Calcula Stochastic RSI corretamente"""
    try:
        closes = pd.Series(prices)
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=periodo_ifr).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=periodo_ifr).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # Stochastic sobre RSI
        rsi_low = rsi.rolling(window=periodo_estocastico).min()
        rsi_high = rsi.rolling(window=periodo_estocastico).max()
        stoch_k_raw = 100 * (rsi - rsi_low) / (rsi_high - rsi_low)

        # Suavização
        stoch_k = stoch_k_raw.rolling(window=suave_k).mean()
        stoch_d = stoch_k.rolling(window=suave_d).mean()

        return stoch_k.iloc[-1], stoch_d.iloc[-1], rsi.iloc[-1]
    except Exception as e:
        print(f"❌ Erro ao calcular Stoch RSI: {e}")
        return None, None, None


async def main():
    """Função principal assíncrona"""
    bot = Bot(token=TOKEN)

    print("="*60)
    print("✅ BOT STOCHASTIC RSI COM STOP LOSS")
    print("📱 TELEGRAM CONECTADO ✅")
    print("📊 COMPRA: %K <= 8")
    print("🛑 VENDA: -$200 (Stop Loss)")
    print("⏱️  Verifica a cada 30 segundos")
    print("="*60)

    contador = 0
    alerta_enviado = False
    preco_entrada = None

    while True:
        try:
            closes = get_btc_price(limit=500)

            if closes is None:
                await asyncio.sleep(30)
                continue

            stoch_k, stoch_d, rsi = calculate_stoch_rsi_correct(closes)

            if stoch_k is None:
                await asyncio.sleep(30)
                continue

            price = closes[-1]
            contador += 1

            status_posicao = "N/A"
            if alerta_enviado and preco_entrada:
                variacao = price - preco_entrada
                status_posicao = f"{variacao:+.2f}"

            print(f"[{contador}] BTC: ${price:.2f} | %K: {stoch_k:.2f} | %D: {stoch_d:.2f} | RSI: {rsi:.2f} | P&L: {status_posicao}")

            # ✅ Sinal de COMPRA (%K <= 8)
            if stoch_k <= 8 and not alerta_enviado:
                msg = f"🟢 COMPRA! BTC: ${price:.2f}\n%K: {stoch_k:.2f} | %D: {stoch_d:.2f}\n(SOBREVENDA - %K <= 8)\n🛑 Stop Loss: ${price - 200:.2f}"
                await enviar_telegram(bot, msg)
                print(f"✅ Alerta COMPRA enviado!")
                alerta_enviado = True
                preco_entrada = price

            # ✅ Sinal de VENDA - STOP LOSS
            elif alerta_enviado and preco_entrada and price <= (preco_entrada - 200):
                perda = price - preco_entrada
                percentual = (perda / preco_entrada) * 100
                msg = f"🔴 VENDA (STOP LOSS)! BTC: ${price:.2f}\n%K: {stoch_k:.2f} | %D: {stoch_d:.2f}\n⚠️ Perda: ${perda:.2f} ({percentual:.2f}%)"
                await enviar_telegram(bot, msg)
                print(f"✅ Alerta VENDA (STOP LOSS) enviado!")
                alerta_enviado = False
                preco_entrada = None

            await asyncio.sleep(30)

        except Exception as e:
            print(f"❌ Erro geral: {e}")
            await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
