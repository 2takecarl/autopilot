from typing import Final, Dict, Set
import asyncio
import aiohttp
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN: Final = '7951462171:AAEGtDbZwBZFNUZbNmPQqOQ2zwUc899b-uA'
BOT_USERNAME: Final = '@xautopilot_bot'

# In-memory storage for user wallets (use database in production)
user_wallets: Dict[int, Set[str]] = {}
tracked_transactions: Dict[str, Set[str]] = {}  # wallet -> set of transaction hashes

# Commands 
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'AI Wallet Tracker 2.0\n\n'
        'Commands:\n'
        '/addwallet <address> - Add wallet to track\n'
        '/removewallet <address> - Remove wallet\n'
        '/list - Show your tracked wallets\n'
        '/help - Show this help message'
    )

async def addwallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not context.args:
        await update.message.reply_text('Please provide a wallet address: /addwallet <address>')
        return
    
    wallet_address = context.args[0].strip()
    
    # Basic validation for Ethereum address
    if not wallet_address.startswith('0x') or len(wallet_address) != 42:
        await update.message.reply_text('Invalid wallet address format. Please provide a valid Ethereum address.')
        return
    
    if user_id not in user_wallets:
        user_wallets[user_id] = set()
    
    if wallet_address in user_wallets[user_id]:
        await update.message.reply_text('Wallet already being tracked!')
        return
    
    user_wallets[user_id].add(wallet_address)
    tracked_transactions[wallet_address] = set()
    
    await update.message.reply_text(f'Added wallet: {wallet_address[:6]}...{wallet_address[-4:]}')

async def removewallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not context.args:
        await update.message.reply_text('Please provide a wallet address: /removewallet <address>')
        return
    
    wallet_address = context.args[0].strip()
    
    if user_id not in user_wallets or wallet_address not in user_wallets[user_id]:
        await update.message.reply_text('Wallet not found in your tracked list!')
        return
    
    user_wallets[user_id].remove(wallet_address)
    if wallet_address in tracked_transactions:
        del tracked_transactions[wallet_address]
    
    await update.message.reply_text(f'Removed wallet: {wallet_address[:6]}...{wallet_address[-4:]}')

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if user_id not in user_wallets or not user_wallets[user_id]:
        await update.message.reply_text('No wallets being tracked. Use /addwallet to add one!')
        return
    
    wallet_list = '\n'.join([f'• {addr[:6]}...{addr[-4:]}' for addr in user_wallets[user_id]])
    await update.message.reply_text(f'Tracked wallets:\n{wallet_list}')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Wallet Tracker Commands:\n\n'
        '/start - Start the bot\n'
        '/addwallet <address> - Add wallet to track\n'
        '/removewallet <address> - Remove wallet\n'
        '/list - Show your tracked wallets\n'
        '/help - Show this help message\n\n'
        'The bot will automatically notify you when tracked wallets make transactions!'
    )

# Transaction monitoring functions
async def get_wallet_transactions(wallet_address: str) -> list:
    """Fetch recent transactions for a wallet using Etherscan API"""
    api_key = "9U6H67B5FWPHGV1311WPX7J4NAXINY3R1D"
    url = f"https://api.etherscan.io/api?module=account&action=txlist&address={wallet_address}&startblock=0&endblock=99999999&page=1&offset=10&sort=desc&apikey={api_key}"
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status') == '1' and 'result' in data:
                        return data['result']
                    else:
                        print(f"API Error: {data.get('message', 'Unknown error')}")
                else:
                    print(f"HTTP Error: {response.status}")
                return []
    except aiohttp.ClientError as e:
        print(f"Connection error: {e}")
        return []
    except Exception as e:
        print(f"Error fetching transactions: {e}")
        return []

async def check_wallet_transactions(app: Application, user_id: int, wallet: str):
    """Check transactions for a specific wallet and user"""
    try:
        transactions = await get_wallet_transactions(wallet)
        
        if not transactions:
            return
            
        for tx in transactions:
            tx_hash = tx.get('hash')
            if not tx_hash:
                continue
                
            # Skip if we've already seen this transaction
            if wallet not in tracked_transactions:
                tracked_transactions[wallet] = set()
                
            if tx_hash in tracked_transactions[wallet]:
                continue
            
            tracked_transactions[wallet].add(tx_hash)
            
            # Determine if it's a buy or sell (simplified logic)
            try:
                value_eth = int(tx.get('value', 0)) / 10**18
                is_outgoing = tx.get('from', '').lower() == wallet.lower()
                
                if value_eth > 0.001:  # Only notify for transactions > 0.001 ETH
                    action = "SOLD" if is_outgoing else "BOUGHT"
                    
                    message = (
                        f"🚨 Wallet Activity Detected!\n\n"
                        f"Wallet: {wallet[:6]}...{wallet[-4:]}\n"
                        f"Action: {action}\n"
                        f"Amount: {value_eth:.4f} ETH\n"
                        f"TX: {tx_hash[:10]}...\n"
                        f"View: https://etherscan.io/tx/{tx_hash}"
                    )
                    
                    await app.bot.send_message(chat_id=user_id, text=message)
                    print(f"Sent notification to user {user_id} for wallet {wallet[:6]}...")
                    
            except (ValueError, KeyError) as e:
                print(f"Error processing transaction data: {e}")
                continue
                
    except Exception as e:
        print(f"Error checking wallet {wallet}: {e}")

async def check_new_transactions(app: Application):
    """Legacy function - replaced by individual wallet checking"""
    pass

async def monitoring_loop(app: Application):
    """Main monitoring loop with better error handling"""
    while True:
        try:
            all_wallets = []
            for user_id, wallets in user_wallets.items():
                for wallet in wallets:
                    all_wallets.append((user_id, wallet))
            
            if all_wallets:
                print(f"Checking {len(all_wallets)} wallets...")
                
                # Rate limiting: Check wallets with delays
                for user_id, wallet in all_wallets:
                    try:
                        await check_wallet_transactions(app, user_id, wallet)
                        await asyncio.sleep(5)  # 5 seconds between requests
                    except Exception as e:
                        print(f"Error checking wallet {wallet}: {e}")
                        continue
                
                # Wait before next cycle based on number of wallets
                cycle_delay = max(60, len(all_wallets) * 3)
                print(f"Cycle complete. Waiting {cycle_delay}s before next check...")
                await asyncio.sleep(cycle_delay)
            else:
                print("No wallets to monitor. Waiting 60 seconds...")
                await asyncio.sleep(60)
                
        except Exception as e:
            print(f"Error in monitoring loop: {e}")
            await asyncio.sleep(120)

# Response handlers
def handle_response(text: str) -> str:
    processed: str = text.lower()

    if 'hello' in processed:
        return 'Hey there! Use /help to see available commands.'
    
    if 'wallet' in processed:
        return 'Use /addwallet to start tracking a wallet!'
    
    return 'Use /help to see available commands.'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    message_type: str = update.message.chat.type
    text: str = update.message.text

    print(f'User ({update.message.chat.id}) in {message_type}: "{text}"')

    if message_type == 'group':
        if BOT_USERNAME in text: 
            new_text: str = text.replace(BOT_USERNAME, '').strip()
            response: str = handle_response(new_text)
        else:
            return
    else:
        response: str = handle_response(text)

    print('Bot:', response)
    await update.message.reply_text(response)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Update {update} caused error {context.error}')

async def main():
    print('Starting Wallet Tracker Bot...')
    app = Application.builder().token(TOKEN).build()

    # Add command handlers
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('addwallet', addwallet_command))
    app.add_handler(CommandHandler('removewallet', removewallet_command))
    app.add_handler(CommandHandler('list', list_command))
    app.add_handler(CommandHandler('help', help_command))

    # Add message handler
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    # Add error handler
    app.add_error_handler(error)

    print('Bot started! Polling for messages...')
    
    # Start the monitoring loop in the background
    monitoring_task = asyncio.create_task(monitoring_loop(app))
    
    # Start polling
    async with app:
        await app.start()
        await app.updater.start_polling(poll_interval=3)
        
        try:
            # Keep the bot running
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            monitoring_task.cancel()
            await app.updater.stop()
            await app.stop()

if __name__ == '__main__':
    asyncio.run(main())