import { StudyDashboard } from "../../components/StudyDashboard";
import { getStudyOverview } from "../../lib/workbench-data";

export default function WorkbenchPage() {
  return <StudyDashboard studyOverviewData={getStudyOverview()} />;
}
