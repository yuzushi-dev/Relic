export const dynamic = 'force-dynamic'
import { StudyDashboard } from "../../../components/StudyDashboard";
import { getStudyOverview } from "../../../lib/workbench-data";

export default function StudyPage() {
  return <StudyDashboard studyOverviewData={getStudyOverview()} />;
}
