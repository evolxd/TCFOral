const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const config = JSON.parse(fs.readFileSync(path.join(root, "tts_config.json"), "utf8"));
const outDir = path.join(root, "audio", "b2");
const ffmpeg = "C:\\Users\\evolx\\node_modules\\@ffmpeg-installer\\win32-x64\\ffmpeg.exe";

const titles = [
  "Présentation personnelle élégante",
  "Études, travail, projet",
  "Ville, quartier, logement",
  "Loisirs et personnalité",
  "Pourquoi le Canada / le français",
  "Réponses courtes prêtes à sortir"
];

function readObject(name, nextMarker) {
  const startMarker = `const ${name} = `;
  const start = html.indexOf(startMarker);
  const end = html.indexOf(nextMarker, start);
  if (start < 0 || end < 0) throw new Error(`Cannot locate ${name}`);
  const source = html.slice(start + startMarker.length, end).trim();
  return Function(`"use strict"; let value; value = ${source}\nreturn value;`)();
}

function safeName(text) {
  return text.normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase()
    .slice(0, 64)
    .replace(/-+$/g, "") || "audio";
}

function legacyName(text) {
  return safeName(Buffer.from(text, "utf8").toString("latin1"));
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function synthesize(text) {
  const response = await fetch(
    `https://api.elevenlabs.io/v1/text-to-speech/${String(config.voice_id).trim()}?output_format=mp3_44100_128`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "xi-api-key": String(config.api_key).trim()
      },
      body: JSON.stringify({
        text,
        model_id: "eleven_multilingual_v2",
        language_code: "fr",
        voice_settings: {
          stability: 0.62,
          similarity_boost: 0.78,
          style: 0.12,
          use_speaker_boost: true,
          speed: Number(config.speed || 0.83)
        }
      })
    }
  );
  if (!response.ok) throw new Error(`ElevenLabs ${response.status}: ${await response.text()}`);
  return Buffer.from(await response.arrayBuffer());
}

function normalizeAudio(filePath) {
  if (!fs.existsSync(ffmpeg)) throw new Error("ffmpeg not found");
  const tempPath = filePath.replace(/\.mp3$/i, ".normalized.mp3");
  const result = spawnSync(ffmpeg, [
    "-hide_banner", "-loglevel", "error", "-y", "-i", filePath,
    "-af", "loudnorm=I=-18:TP=-1.5:LRA=11",
    "-ar", "44100", "-b:a", "128k", tempPath
  ], { encoding: "utf8" });
  if (result.status !== 0) throw new Error(result.stderr || `ffmpeg failed for ${filePath}`);
  fs.renameSync(tempPath, filePath);
}

async function main() {
  fs.mkdirSync(outDir, { recursive: true });
  const drafts = readObject("b2FinalDrafts", "\n\nfunction lines");
  const questions = readObject("tache1CardQuestions", "\n\nconst tache1B2KeyPoints");
  const tasks = [];

  titles.forEach((title, cardIndex) => {
    const titleSlug = legacyName(title);
    drafts[title].fr.forEach((sentence, sentenceIndex) => {
      const name = `tache1-${String(cardIndex + 1).padStart(2, "0")}-${titleSlug}-${String(sentenceIndex + 1).padStart(2, "0")}-${safeName(sentence)}.mp3`;
      tasks.push({ text: sentence, filePath: path.join(outDir, name) });
    });
    questions[title].forEach((question, questionIndex) => {
      const name = `teacher-tache1-${String(cardIndex + 1).padStart(2, "0")}-${String(questionIndex + 1).padStart(2, "0")}-${safeName(question.fr)}.mp3`;
      tasks.push({ text: question.fr, filePath: path.join(outDir, name) });
    });
  });

  const copyArg = process.argv.indexOf("--copy-to");
  if (copyArg >= 0) {
    const destination = process.argv[copyArg + 1];
    if (!destination) throw new Error("--copy-to requires a destination directory");
    fs.mkdirSync(destination, { recursive: true });
    tasks.forEach(task => fs.copyFileSync(task.filePath, path.join(destination, path.basename(task.filePath))));
    console.log(`Copied ${tasks.length} dialogue files to ${destination}.`);
  }

  const missing = tasks.filter(task => !fs.existsSync(task.filePath));
  console.log(`Dialogue audio: ${missing.length} new, ${tasks.length - missing.length} already present.`);
  for (let index = 0; index < missing.length; index += 1) {
    const task = missing[index];
    console.log(`[${index + 1}/${missing.length}] ${path.basename(task.filePath)}`);
    fs.writeFileSync(task.filePath, await synthesize(task.text));
    normalizeAudio(task.filePath);
    await sleep(450);
  }
}

main().catch(error => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
