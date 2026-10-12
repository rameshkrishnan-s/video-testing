/**
 * Scene id -> component. Main and the per-scene "Scene-<id>" compositions read this map.
 * Scene agents replace the component files; this map should not need edits.
 */
import type React from "react";
import type { SceneId } from "../lib/timeline";
import { NightSky } from "./NightSky";
import { PullBack } from "./PullBack";
import { Karman } from "./Karman";
import { Orbit } from "./Orbit";
import { StarStuff } from "./StarStuff";
import { Question } from "./Question";
import { Psych } from "./Psych";
import { Someday } from "./Someday";
import { Already } from "./Already";

export const SCENE_COMPONENTS: Record<SceneId, React.FC> = {
  "night-sky": NightSky,
  "pull-back": PullBack,
  karman: Karman,
  orbit: Orbit,
  "star-stuff": StarStuff,
  question: Question,
  psych: Psych,
  someday: Someday,
  already: Already,
};
