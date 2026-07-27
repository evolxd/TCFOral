const fs = require("fs");

const html = fs.readFileSync("index.html", "utf8");

function section(start, end) {
  const from = html.indexOf(start);
  const to = html.indexOf(end, from + start.length);
  if (from < 0 || to < 0) throw new Error(`Could not locate ${start} -> ${end}`);
  return html.slice(from, to);
}

const gapHelper = section("function schedulePlaybackGap", "function applyPlaybackRate");
if (!gapHelper.includes("currentLoopGapMs()")) {
  throw new Error("Shared playback gap does not use the saved interval setting.");
}

const speakItem = section("async function speakItem", "async function playCardDialogue");
if (!speakItem.includes("schedulePlaybackGap(playbackToken, playCurrent)")) {
  throw new Error("Normal sentence reading does not wait between sentences.");
}
if (speakItem.includes("if (!loop) {\n      playCurrent()")) {
  throw new Error("Normal reading still bypasses the sentence gap.");
}

const dialogue = section("async function playCardDialogue", "async function playSingleSentence");
if (!dialogue.includes("if (playedQuestion && hasAudioAfterQuestion)")) {
  throw new Error("Examiner question and learner answer do not share the configured gap.");
}
if (!dialogue.includes("schedulePlaybackGap(playbackToken, () => playSegment(segmentIndex + 1))")) {
  throw new Error("Dialogue segments do not wait before the next prompt.");
}

const clickHandler = section('if (nextLoopBtn) {', 'if (downloadBtn) {');
for (const required of [
  "nextVisibleCardIndex(index)",
  "scrollToCard(nextIndex)",
  "playCardDialogue(templates[nextIndex], nextIndex"
]) {
  if (!clickHandler.includes(required)) throw new Error(`Next-card reading is missing: ${required}`);
}

if (!html.includes("下一步：朗读下一卡 ▶")) {
  throw new Error("The next-card button does not state that it starts reading.");
}

console.log(JSON.stringify({
  sharedGapForReadAndLoop: true,
  examinerAnswerGap: true,
  dialogueSegmentGap: true,
  nextCardStartsReading: true
}));
