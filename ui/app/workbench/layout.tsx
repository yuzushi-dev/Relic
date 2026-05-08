import { WorkbenchShell } from "../../components/WorkbenchShell";
import { getStudyOverview } from "../../lib/workbench-data";

export const dynamic = "auto";

export default function WorkbenchLayout({ children }: { children: React.ReactNode }) {
  return <WorkbenchShell studyOverviewData={getStudyOverview()}>{children}</WorkbenchShell>;
}
