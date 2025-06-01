from typing import Final
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN: Final = '7951462171:AAEGtDbZwBZFNUZbNmPQqOQ2zwUc899b-uA'
BOT_USERNAME: Final = '@xautopilot_bot'

#Commands 
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('AI N.I.G.G.A. WALLET TRACKER 2.0')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('wallet tracker')

async def custom_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('custom command')


#responses

def handle_response(text: str) -> str:
    processed: str = text.lower()

    if 'hello' in processed:
        return 'yo'

    if 'race' in processed:
        return 'Gurt'

    if 'yogurt' in processed:
        return 'gurt: yo'

    return 'gurt: idk twn'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    message_type: str = update.message.chat.type
    text: str = update.message.text

    print(f'User ({update.message.chat.id}) in {message_type}: "{text}')

    #remove this section up until -response: str = handle_response(text)- if bot should work the same in a group (keep -if BOT_USERNAME in text- tough)
    if message_type == 'group':
        if BOT_USERNAME in text: 
            new_tex: str = text.replace(BOT_USERNAME, '').strip()
            response: str = handle_response(new_tex)
        else:
            return
    else:
        response: str = handle_response(text)

    print('Bot:', response)
    await update.message.reply_text(response)


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Update {update} caused error {context.error}')


if __name__ == '__main__':
    print('Starting...')
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('custom', custom_command))

    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    app.add_error_handler(error)

    print('Polling...')
    app.run_polling(poll_interval=3)