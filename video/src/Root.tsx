import React from "react";
import { Composition, Folder, Still } from "remotion";
import { Logo } from "./brand/Logo";
import { Banner } from "./brand/Banner";
import { Main, ScenePreview } from "./Main";
import { EarthTest, EARTH_TEST_FRAMES } from "./dev/EarthTest";
import { DesignDemo, DESIGN_DEMO_FRAMES } from "./dev/DesignDemo";
import { PerfTest } from "./dev/PerfTest";
import { getScene } from "./lib/timeline";
import { VIDEO } from "./lib/theme";
import "./lib/fonts";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Main"
        component={Main}
        durationInFrames={VIDEO.durationInFrames}
        fps={VIDEO.fps}
        width={VIDEO.width}
        height={VIDEO.height}
      />
      <Folder name="Scenes">
        <Composition
          id="Scene-night-sky"
          component={ScenePreview}
          durationInFrames={getScene("night-sky").durationInFrames}
          fps={VIDEO.fps}
          width={VIDEO.width}
          height={VIDEO.height}
          defaultProps={{ id: "night-sky" as const }}
        />
        <Composition
          id="Scene-pull-back"
          component={ScenePreview}
          durationInFrames={getScene("pull-back").durationInFrames}
          fps={VIDEO.fps}
          width={VIDEO.width}
          height={VIDEO.height}
          defaultProps={{ id: "pull-back" as const }}
        />
        <Composition
          id="Scene-karman"
          component={ScenePreview}
          durationInFrames={getScene("karman").durationInFrames}
          fps={VIDEO.fps}
          width={VIDEO.width}
          height={VIDEO.height}
          defaultProps={{ id: "karman" as const }}
        />
        <Composition
          id="Scene-orbit"
          component={ScenePreview}
          durationInFrames={getScene("orbit").durationInFrames}
          fps={VIDEO.fps}
          width={VIDEO.width}
          height={VIDEO.height}
          defaultProps={{ id: "orbit" as const }}
        />
        <Composition
          id="Scene-star-stuff"
          component={ScenePreview}
          durationInFrames={getScene("star-stuff").durationInFrames}
          fps={VIDEO.fps}
          width={VIDEO.width}
          height={VIDEO.height}
          defaultProps={{ id: "star-stuff" as const }}
        />
        <Composition
          id="Scene-question"
          component={ScenePreview}
          durationInFrames={getScene("question").durationInFrames}
          fps={VIDEO.fps}
          width={VIDEO.width}
          height={VIDEO.height}
          defaultProps={{ id: "question" as const }}
        />
        <Composition
          id="Scene-psych"
          component={ScenePreview}
          durationInFrames={getScene("psych").durationInFrames}
          fps={VIDEO.fps}
          width={VIDEO.width}
          height={VIDEO.height}
          defaultProps={{ id: "psych" as const }}
        />
        <Composition
          id="Scene-someday"
          component={ScenePreview}
          durationInFrames={getScene("someday").durationInFrames}
          fps={VIDEO.fps}
          width={VIDEO.width}
          height={VIDEO.height}
          defaultProps={{ id: "someday" as const }}
        />
        <Composition
          id="Scene-already"
          component={ScenePreview}
          durationInFrames={getScene("already").durationInFrames}
          fps={VIDEO.fps}
          width={VIDEO.width}
          height={VIDEO.height}
          defaultProps={{ id: "already" as const }}
        />
      </Folder>
      <Folder name="Dev">
        <Composition
          id="EarthTest"
          component={EarthTest}
          durationInFrames={EARTH_TEST_FRAMES}
          fps={VIDEO.fps}
          width={VIDEO.width}
          height={VIDEO.height}
        />
        <Composition
          id="DesignDemo"
          component={DesignDemo}
          durationInFrames={DESIGN_DEMO_FRAMES}
          fps={VIDEO.fps}
          width={VIDEO.width}
          height={VIDEO.height}
        />
        <Composition
          id="PerfTest"
          component={PerfTest}
          durationInFrames={60}
          fps={VIDEO.fps}
          width={VIDEO.width}
          height={VIDEO.height}
          defaultProps={{}}
        />
      </Folder>
    <Folder name="Brand">
        <Still id="Logo" component={Logo} width={800} height={800} />
        <Still id="Banner" component={Banner} width={2560} height={1440} />
      </Folder>
    </>
  );
};
