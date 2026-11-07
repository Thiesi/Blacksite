# Door and service protocol upgrades

Upgrade the door and service together. S41's tolerance for additive server
frames is recovery behavior, not support for running mismatched versions.
S41 must be installed in an earlier upgrade than P11: a door older than
S41 still reconnects on an unknown frame, even if the new service also
contains S41.

After its welcome handshake, an S41 door ignores unknown server frame
types. It emits an INFO diagnostic once per type per door launch through
`blacksite.door.connection` when a host enables standard Python logging.
The door configures no console handler and sends no diagnostic to the
game terminal.

An unknown view kind leaves the last screen visible. Its revision and
following deltas are not acknowledged or applied. A later known full view
restores updates. The door sends no repeated resync requests for this
case; continued full snapshots may come from ordinary server flow control.
If the screen stays stale during a mismatched installation, complete the
door/service upgrade. Known malformed frames, an incompatible protocol
major and an invalid first handshake frame still disconnect.
