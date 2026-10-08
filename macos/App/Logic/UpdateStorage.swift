import Foundation

/// A failed measurement blocks the update just like insufficient capacity.
enum UpdateStorageIssue: String { case lowSpace, lowInodes, unavailable }

/// Same six measurements and reserves as scripts/kingfisher_update_storage.py.
struct UpdateStorageStatus: Decodable {
    let root_available_bytes: UInt64
    let root_available_inodes: UInt64
    let data_available_bytes: UInt64
    let data_available_inodes: UInt64
    let backup_bytes: UInt64
    let backup_files: UInt64

    static func parse(_ output: String) -> UpdateStorageStatus? {
        guard let data = output.data(using: .utf8),
              let fields = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              Set(fields.keys) == Set(["root_available_bytes", "root_available_inodes", "data_available_bytes",
                                       "data_available_inodes", "backup_bytes", "backup_files"]),
              fields.values.allSatisfy({ value in
                  guard let number = value as? NSNumber else { return false }
                  // JSONDecoder rejects booleans/negative/overflow; also reject floating-point tokens.
                  return !["d", "f"].contains(String(cString: number.objCType))
              }) else { return nil }
        return try? JSONDecoder().decode(UpdateStorageStatus.self, from: data)
    }

    func issue(beforeBackup: Bool) -> UpdateStorageIssue? {
        let reserve: UInt64 = 512 * 1024 * 1024
        let copies: UInt64 = beforeBackup ? 3 : 2
        let (bytes, bytesOverflow) = backup_bytes.multipliedReportingOverflow(by: copies)
        let (files, filesOverflow) = backup_files.multipliedReportingOverflow(by: copies)
        let (neededBytes, reserveOverflow) = bytes.addingReportingOverflow(reserve)
        let (neededFiles, inodeOverflow) = files.addingReportingOverflow(64)
        guard !bytesOverflow, !filesOverflow, !reserveOverflow, !inodeOverflow else { return .unavailable }
        if root_available_bytes < reserve || data_available_bytes < neededBytes { return .lowSpace }
        if root_available_inodes < 64 || data_available_inodes < neededFiles { return .lowInodes }
        return nil
    }
}
