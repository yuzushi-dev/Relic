export const dynamic = process.env.RELIC_UI_BUILD_TARGET === 'static' ? 'force-static' : 'force-dynamic';
import { StudyDashboard } from "../../components/StudyDashboard";
import { getStudyOverview } from "../../lib/workbench-data";

export default function WorkbenchPage() {
  return <StudyDashboard studyOverviewData={getStudyOverview()} />;
}
