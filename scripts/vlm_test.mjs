import ZAI from '/home/z/.bun/install/global/node_modules/z-ai-web-dev-sdk/dist/index.js';
import fs from 'fs';

const img = fs.readFileSync('/home/z/my-project/scripts/captcha_inst_6x.png').toString('base64');

async function main() {
  const zai = await ZAI.create();
  const completion = await zai.chat.completions.create({
    messages: [
      {
        role: 'user',
        content: [
          { type: 'image_url', image_url: { url: `data:image/png;base64,${img}` } },
          { type: 'text', text: 'This shows a captcha instruction bar with red icons in a row. List each icon you see from left to right with a one-word name for each.' }
        ]
      }
    ],
    thinking: { type: 'disabled' }
  });
  console.log('RESPONSE:', completion.choices[0]?.message?.content);
}
main().catch(e => { console.error('ERR:', e.message); process.exit(1); });
