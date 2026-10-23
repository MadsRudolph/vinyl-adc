import {Composition} from 'remotion';
import {Short,TOTAL} from './Short';
import {Scope,SCOPE_TOTAL} from './Scope';
import {Story,STORY_TOTAL} from './Story';
import {Cine,CINE_TOTAL} from './Cine';
export const Root:React.FC=()=>(<>
  <Composition id="Short" component={Short} durationInFrames={TOTAL} fps={30} width={1080} height={1920}/>
  <Composition id="Scope" component={Scope} durationInFrames={SCOPE_TOTAL} fps={30} width={1080} height={1920}/>
  <Composition id="Story" component={Story} durationInFrames={STORY_TOTAL} fps={30} width={1080} height={1920}/>
  <Composition id="Cine" component={Cine} durationInFrames={CINE_TOTAL} fps={30} width={1080} height={1920}/>
</>);
