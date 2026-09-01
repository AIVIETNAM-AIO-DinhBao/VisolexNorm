export type DiffSegmentType = 'equal' | 'changed' | 'inserted' | 'deleted';

export interface DiffSegment {
  text: string;
  type: DiffSegmentType;
  groupId?: number;
}

export interface DiffResult {
  originalSegments: DiffSegment[];
  normalizedSegments: DiffSegment[];
  hasChanges: boolean;
}

interface ParsedToken {
  prefix: string;
  text: string;
}

interface ParsedText {
  items: ParsedToken[];
  trailing: string;
}

/**
 * Remove Vietnamese diacritics and normalize to lower-case ASCII for heuristic similarity.
 */
function stripDiacritics(str: string): string {
  return str
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase();
}

/**
 * Standard Levenshtein distance on normalized strings.
 */
function levenshtein(a: string, b: string): number {
  const n = a.length;
  const m = b.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));

  for (let i = 0; i <= n; i++) dp[i][0] = i;
  for (let j = 0; j <= m; j++) dp[0][j] = j;

  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      if (a[i - 1] === b[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1];
      } else {
        dp[i][j] = 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
      }
    }
  }

  return dp[n][m];
}

/**
 * Normalized token similarity score in [0.0, 1.0] between source and target token chunks.
 */
function tokenSimilarity(srcWords: string[], tgtWords: string[]): number {
  const sFull = srcWords.map((w) => stripDiacritics(w)).join(' ');
  const sNoSpace = srcWords.map((w) => stripDiacritics(w)).join('');
  const tFull = tgtWords.map((w) => stripDiacritics(w)).join(' ');
  const tNoSpace = tgtWords.map((w) => stripDiacritics(w)).join('');

  if (sFull === tFull || sNoSpace === tNoSpace) {
    return 1.0;
  }

  // Initials match (e.g. hs -> hoc sinh, k -> khong, cx -> cung)
  const tgtInitials = tgtWords.map((w) => stripDiacritics(w)[0] || '').join('');
  if (sNoSpace === tgtInitials) {
    return 0.95;
  }

  // Partial acronym / contraction check (e.g. hqua -> hom qua)
  if (tgtWords.length > 1 && srcWords.length === 1) {
    const s = sNoSpace;
    const firstInit = stripDiacritics(tgtWords[0])[0] || '';
    const rest = tgtWords.slice(1).map((w) => stripDiacritics(w)).join('');
    if (s === firstInit + rest) {
      return 0.92;
    }
  }

  // Levenshtein similarity
  const levDist = Math.min(levenshtein(sNoSpace, tNoSpace), levenshtein(sFull, tFull));
  const maxLen = Math.max(sNoSpace.length, tNoSpace.length, 1);
  const levSim = Math.max(0, 1 - levDist / maxLen);

  // Consonant skeleton match (e.g. bt -> biet, cx -> cung, hc -> hoc)
  const sCons = sNoSpace.replace(/[aeiouy]/g, '');
  const tCons = tNoSpace.replace(/[aeiouy]/g, '');
  if (sCons && sCons === tCons) {
    return Math.max(levSim, 0.85);
  }

  return levSim;
}

/**
 * Tokenize text into lexical tokens (words and punctuation), preserving preceding whitespace.
 */
function parseLexicalTokens(text: string): ParsedText {
  const tokenRegex = /([^\S\r\n]*|\r?\n)([^\s\p{P}]+|[\p{P}])/gu;
  const items: ParsedToken[] = [];
  let match: RegExpExecArray | null;
  let lastIndex = 0;

  while ((match = tokenRegex.exec(text)) !== null) {
    items.push({
      prefix: match[1],
      text: match[2],
    });
    lastIndex = tokenRegex.lastIndex;
  }

  const trailing = text.slice(lastIndex);
  return { items, trailing };
}

interface LocalAlignmentPair {
  src: number[];
  tgt: number[];
}

/**
 * Level 2: Local dynamic-programming alignment for an unmatched region between anchors.
 */
function alignLocalRegion(srcTokens: string[], tgtTokens: string[]): LocalAlignmentPair[] {
  const n = srcTokens.length;
  const m = tgtTokens.length;

  if (n === 0) {
    return [{ src: [], tgt: tgtTokens.map((_, i) => i) }];
  }
  if (m === 0) {
    return [{ src: srcTokens.map((_, i) => i), tgt: [] }];
  }

  interface DPNode {
    score: number;
    pi: number;
    pj: number;
  }

  const dp: DPNode[][] = Array.from({ length: n + 1 }, () =>
    Array.from({ length: m + 1 }, () => ({ score: -Infinity, pi: -1, pj: -1 }))
  );
  dp[0][0] = { score: 0, pi: -1, pj: -1 };

  for (let i = 0; i <= n; i++) {
    for (let j = 0; j <= m; j++) {
      if (dp[i][j].score === -Infinity) continue;
      const currentScore = dp[i][j].score;

      // Block matching: k source tokens with l target tokens
      for (let k = 1; k <= Math.min(3, n - i); k++) {
        for (let l = 1; l <= Math.min(3, m - j); l++) {
          const sSlice = srcTokens.slice(i, i + k);
          const tSlice = tgtTokens.slice(j, j + l);
          const sim = tokenSimilarity(sSlice, tSlice);
          const gain = sim * 10 - Math.abs(k - l) * 0.5;
          const nextScore = currentScore + gain;

          if (nextScore > dp[i + k][j + l].score) {
            dp[i + k][j + l] = { score: nextScore, pi: i, pj: j };
          }
        }
      }

      // Deletion (source step)
      if (i < n) {
        const delScore = currentScore - 1.0;
        if (delScore > dp[i + 1][j].score) {
          dp[i + 1][j] = { score: delScore, pi: i, pj: j };
        }
      }

      // Insertion (target step)
      if (j < m) {
        const insScore = currentScore - 1.0;
        if (insScore > dp[i][j + 1].score) {
          dp[i][j + 1] = { score: insScore, pi: i, pj: j };
        }
      }
    }
  }

  // Backtrack to find optimal local segment pairs
  const pairs: LocalAlignmentPair[] = [];
  let currI = n;
  let currJ = m;

  while (currI > 0 || currJ > 0) {
    const node = dp[currI][currJ];
    const prevI = node.pi;
    const prevJ = node.pj;
    if (prevI === -1 && prevJ === -1) break;

    const srcIndices: number[] = [];
    for (let x = prevI; x < currI; x++) srcIndices.push(x);
    const tgtIndices: number[] = [];
    for (let y = prevJ; y < currJ; y++) tgtIndices.push(y);

    pairs.push({ src: srcIndices, tgt: tgtIndices });
    currI = prevI;
    currJ = prevJ;
  }

  pairs.reverse();
  return pairs;
}

interface DiffBlock {
  type: 'anchor' | 'diff';
  srcIndices: number[];
  tgtIndices: number[];
}

/**
 * Compare original and normalized text and produce structured diff segments
 * with matching group IDs for corresponding changed spans using a two-level alignment:
 *
 * Level 1: Global exact lexical anchors (no whitespace participation).
 * Level 2: Local dynamic-programming alignment for unmatched regions between anchors.
 */
export function computeTextDiff(originalText: string, normalizedText: string): DiffResult {
  if (!originalText && !normalizedText) {
    return { originalSegments: [], normalizedSegments: [], hasChanges: false };
  }

  if (originalText === normalizedText) {
    return {
      originalSegments: [{ text: originalText, type: 'equal' }],
      normalizedSegments: [{ text: normalizedText, type: 'equal' }],
      hasChanges: false,
    };
  }

  const srcParsed = parseLexicalTokens(originalText);
  const tgtParsed = parseLexicalTokens(normalizedText);
  const sItems = srcParsed.items;
  const tItems = tgtParsed.items;
  const sWords = sItems.map((x) => x.text);
  const tWords = tItems.map((x) => x.text);

  // LEVEL 1: LCS of exact lexical tokens (whitespace does NOT participate as anchor)
  const n = sWords.length;
  const m = tWords.length;
  const lcsDP: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));

  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      if (sWords[i - 1] === tWords[j - 1]) {
        lcsDP[i][j] = lcsDP[i - 1][j - 1] + 1;
      } else {
        lcsDP[i][j] = Math.max(lcsDP[i - 1][j], lcsDP[i][j - 1]);
      }
    }
  }

  interface Anchor {
    sIdx: number;
    tIdx: number;
  }

  const anchors: Anchor[] = [];
  let ai = n;
  let aj = m;

  while (ai > 0 && aj > 0) {
    if (sWords[ai - 1] === tWords[aj - 1]) {
      anchors.push({ sIdx: ai - 1, tIdx: aj - 1 });
      ai--;
      aj--;
    } else if (lcsDP[ai - 1][aj] >= lcsDP[ai][aj - 1]) {
      ai--;
    } else {
      aj--;
    }
  }
  anchors.reverse();

  // LEVEL 2: Build aligned blocks
  const blocks: DiffBlock[] = [];
  let lastS = 0;
  let lastT = 0;

  for (const anchor of anchors) {
    if (lastS < anchor.sIdx || lastT < anchor.tIdx) {
      const sSlice = sWords.slice(lastS, anchor.sIdx);
      const tSlice = tWords.slice(lastT, anchor.tIdx);
      const pairs = alignLocalRegion(sSlice, tSlice);
      for (const p of pairs) {
        blocks.push({
          type: 'diff',
          srcIndices: p.src.map((idx) => lastS + idx),
          tgtIndices: p.tgt.map((idx) => lastT + idx),
        });
      }
    }

    blocks.push({
      type: 'anchor',
      srcIndices: [anchor.sIdx],
      tgtIndices: [anchor.tIdx],
    });

    lastS = anchor.sIdx + 1;
    lastT = anchor.tIdx + 1;
  }

  if (lastS < sWords.length || lastT < tWords.length) {
    const sSlice = sWords.slice(lastS);
    const tSlice = tWords.slice(lastT);
    const pairs = alignLocalRegion(sSlice, tSlice);
    for (const p of pairs) {
      blocks.push({
        type: 'diff',
        srcIndices: p.src.map((idx) => lastS + idx),
        tgtIndices: p.tgt.map((idx) => lastT + idx),
      });
    }
  }

  // Convert blocks into segment streams with exact whitespace reconstruction
  const originalSegments: DiffSegment[] = [];
  const normalizedSegments: DiffSegment[] = [];
  let groupId = 1;
  let hasChanges = false;

  function emitEqual(origStr: string, normStr: string) {
    if (origStr) originalSegments.push({ text: origStr, type: 'equal' });
    if (normStr) normalizedSegments.push({ text: normStr, type: 'equal' });
  }

  for (const block of blocks) {
    if (block.type === 'anchor') {
      const sIdx = block.srcIndices[0];
      const tIdx = block.tgtIndices[0];
      const sToken = sItems[sIdx];
      const tToken = tItems[tIdx];

      // Emit prefix whitespace if any
      emitEqual(sToken.prefix, tToken.prefix);
      // Emit anchor token
      originalSegments.push({ text: sToken.text, type: 'equal' });
      normalizedSegments.push({ text: tToken.text, type: 'equal' });
    } else {
      hasChanges = true;
      const gid = groupId++;
      const sIdxs = block.srcIndices;
      const tIdxs = block.tgtIndices;

      // Common prefix space before this diff block
      const sFirstPrefix = sIdxs.length > 0 ? sItems[sIdxs[0]].prefix : '';
      const tFirstPrefix = tIdxs.length > 0 ? tItems[tIdxs[0]].prefix : '';
      emitEqual(sFirstPrefix, tFirstPrefix);

      // Source text inside block
      let sText = '';
      for (let k = 0; k < sIdxs.length; k++) {
        const item = sItems[sIdxs[k]];
        sText += (k > 0 ? item.prefix : '') + item.text;
      }

      // Target text inside block
      let tText = '';
      for (let k = 0; k < tIdxs.length; k++) {
        const item = tItems[tIdxs[k]];
        tText += (k > 0 ? item.prefix : '') + item.text;
      }

      if (sText && tText) {
        originalSegments.push({ text: sText, type: 'changed', groupId: gid });
        normalizedSegments.push({ text: tText, type: 'changed', groupId: gid });
      } else if (sText) {
        originalSegments.push({ text: sText, type: 'deleted', groupId: gid });
      } else if (tText) {
        normalizedSegments.push({ text: tText, type: 'inserted', groupId: gid });
      }
    }
  }

  // Trailing whitespace
  emitEqual(srcParsed.trailing, tgtParsed.trailing);

  return { originalSegments, normalizedSegments, hasChanges };
}
