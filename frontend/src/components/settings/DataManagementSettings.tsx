import DataBackupCard from './DataBackupCard';
import DataCleanupCard from './DataCleanupCard';
import DataRestoreCard from './DataRestoreCard';
import DataStorageUsageCard from './DataStorageUsageCard';
import JobRecoverySettingsCard from './JobRecoverySettingsCard';

export default function DataManagementSettings() {
  return (
    <div className="grid gap-5">
      <DataStorageUsageCard />
      <JobRecoverySettingsCard />
      <DataBackupCard />
      <DataRestoreCard />
      <DataCleanupCard />
    </div>
  );
}
