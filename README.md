```text
IEC501A M ddd,ser [,labtyp](,den),jjj,sss[,dsn]
IEC501E M ddd,ser [,labtyp](,den),jjj,sss[,dsn]
```

**Explanation**: `M` indicates that a volume is to be mounted on
device ***ddd***:

* If ***ser*** is a 6-digit serial number, the volume with that serial
number is to be mounted on device ***ddd***.
* If ***ser*** is `SCRTCH`, a public scratch volume is to be mounted.
* If ***ser*** is `PRIVAT`, a private scratch volume is to be mounted.
* If ***ser*** begins with `L`, the volume to be mounted is unlabeled;
the number after the first character is an internal serial
number assigned by the system to an unlabeled volume.
The internal serial is of the form `Lxxxyy` where `xxx` is the
data set number (0-999) and `yy` is the volume sequence
number (0-99). The numbers are recycled after they reach
the limit.
  
In the message text, ***labtyp*** indicates the label type of the
mounted volume (either `SL`, `NL`, `AL`, or `NSL`) and will appear
for tape volumes only.

…

**System Action:** If the message ID is `IEC501A`, the job step waits
for the volume to be mounted or until the task reaches time-out.
If the message ID is `IEC501E`, the volume indicated by ***ser*** is the
next volume to be processed after the system finishes processing
on the current volume.

**Operator Response:** If ***ser*** is `SCRTCH` or `PRIVAT` and ***ddd*** is a
tape unit, make sure that the file protection ring has been
inserted in the volume.

Mount the volume on the device. If ser is `SCRTCH` or `PRIVAT`
and a scratch volume is already on the device, mount another
scratch volume. Then ready the device.

---

```text
IEC502E n ddd,ser [,labtyp][,ddn-c][,SPACE=ccccc,tttt,aaaa/cccc,tttt],jjj,sss[,dsn]
```

**Explanation:** The volume on device ***ddd*** is to have a disposition
of n, where n is one of the following:

|n|Meaning|
|-|-|
|K|Implies PRIVATE volume; the volume is to be demounted and returned to the library.|
|D|Implies PUBLIC volume; the volume is to be demounted and used as a scratch volume when the job ends.|
|RK|Implies PRIVATE-RETAIN volume; the volume is to be demounted and retained near the system for future use. In the event that the job ends and the volume has not been remounted, return it to the library.|
|RD|Implies PUBLIC-RETAIN volume; the volume is to be demounted and retained near the system for future use. In the event that the job ends and the volume has not been remounted, it may be used as a scratch volume.|
|R|Implies RETAIN volume; the volume is to be demounted and retained near the system for future use. In the event that the job ends and the volume has not been remounted, the operator must determine what disposition to give to the .volume. This message will appear if a volume isrejected because it is not the volume requested (for example, a conflict in the label, label type, or density).

If ***ser*** is blank, O/C/EOV look-ahead mount has found an
unverified (UCBVOLI = ZEROS) volume already mounted on the
next available unit. Operator intervention is required to verify
that the proper volume is mounted.

If ***ser*** is a 6-digit serial number, the volume with that serial
number is to be demounted from the device.

If ***ser*** begins with L, the volume to be demounted is unlabeled;
the number after the first character is an internal serial number
assigned by the system to an unlabeled volume. The internal
serial number is of the form `Laaabb` where `aaa` is the data set
number (0-999) and `bb` is the volume sequence number (0-99).
The numbers are recycled after they reach the limit.

In the message text, ***labtyp*** indicates the label type of the
demounted volume (either SL, AL, NL, or NSL) and will appear
for tape volumes only).

If ***ddn-c*** appears in the message text, the volume to be
demounted is a tape recorded in ASCII; ***ddn*** specifies the ddname
of the JCL requesting the volume and *c* specifies the reason for
demounting:

…

**System Action:** If the device is a tape drive, the volume is
unloaded. If the device is a direct access unit, the system inhibits
I/O to the device.

**Operator Response:** Demount the volume, mark the serial
number and label type on it, and dispose of it as indicated. If
LSPACE-PERMANENT I/O ERROR appears in the message
text, a permanent I/O error was encountered while trying to read
the VTOC. Execute the IEHLIST utility program to list the
VTOC of the volume specified by ser or ddd.

…

---

```text
IEF233A M ddd,ser,[labtyp],jjj[,sss[,dsn]]
```

**Explanation:** `M` indicates that a volume is to be mounted on
device ddd. The volume is required by job ***jjj*** or, if applicable,
step ***sss*** of job ***jjj***. (If this message is issued for a system task, ***sss***
will appear as a system task identifier.)

…

* If ***ser*** is a 6-digit serial number, the volume with that serial
number is to be mounted on device ***ddd***.
* If ***ser*** is `SCRTCH`, a scratch volume is to be mounted. A
scratch tape volume must have the label type specified by
***labtyp***: `SL` for standard label or standard user label, `NSL` for
non-standard label, or `NL` for no label or by-pass label.
* If ***ser*** is `PRIVAT`, a private volume is to be mounted. It will
be marked PRIVATE and demounted at the end of job ***jjj***.
* If ***ser*** begins with an `L`, the volume to be mounted is
unlabeled; the number after the `L` is an internal serial
number assigned by the system to an unlabeled volume and is of 
the form `xxxyy`, where
`xxx` is the data set number and `yy` is the volume sequence
number for the data set.

**System Action:** The task waits for the volume to be mounted if
the device is direct access. If a scratch volume is to be mounted,
all other jobs requiring the same device group will not be
allocated until the operator responds to this message.

**Operator Response**: For tape, if ***ser*** is `SCRTCH` or `PRIVAT`,
make sure that the file protect ring has been inserted in the
volume.

Mount volume ***ser*** on the device; then ready device ***ddd***. If a
mount is requested for a device with non-removable volumes,
ready the device in order to indicate that the volume is mounted.
If the volume cannot be mounted, enter a `CANCEL` command to
terminate job ***jjj***. Separate commands are necessary to cancel all
jobs requiring volume ***ser***.


---

```text
IEF233D M ddd,ser,[labtyp],jjj[,sss[,dsn]]
OR RESPOND TO IEF455D MESSAGE
```

**Explanation:** `M` indicates that a volume is to be mounted on
device ***ddd***. The mount is required for a dynamic allocation for
step ***sss*** of job ***jjj***.

…

* If ***ser*** is a 6-digit serial number, the volume with that serial
number is to be mounted on the device.
* If ***ser*** is `SCRTCH`, a scratch volume is to be mounted. A
scratch tape volume must have the label type specified by
***labtyp***: `SL` for standard label or standard user label, `NL` for
no label or bypass label, or `AL` for ANSI label.
* If ***ser*** is `PRIVAT`, a private volume is to be mounted.
* If ***ser*** begins with an `L`, the volume to be mounted is
unlabeled. The number after the `L` is an internal serial
number assigned by the system in the form of `xxxyy`, where
`xxx` is the data set number and `yy` is the volume sequence
number for the data set.

**System Action:** The task waits for the volume to be mounted or
for the operator to reply NO to message IEF455D. The job will
not proceed until the operator responds to this message.

**Operator Response:** If the required volume is available, mount it
and ready device ***ddd***. If a mount is requested for a device with a
non-removable volume, ready device ***ddd***.

For tape, if ***ser*** is `SCRTCH` or `PRIVAT`, make sure the file
protect ring has been inserted in the volume.

If for any reason the volume cannot be mounted, reply `NO`. A
reply of `NO` to this message also serves as a reply of `NO` to any
other mount message for step ***sss*** of job ***jjj***.

---

```text
IEF234E {K|D|R} dev[,ser,text2,jobname[,stepname]]
```

**Explanation**: `K` indicates that the volume is to be demounted and
returned to the library. `R` indicates that the volume on device ***ddd***
is to be demounted and retained near the computer for use in the
near future; `D` indicates that the volume is to be demounted and
used subsequently as a scratch volume:
* If ***ser*** is a 6-digit number, it is the serial number of the
volume, which contains labels.
* If ***ser*** begins with `L`, the volume to be demounted is
unlabeled; the number after the `L` is an internal serial
number assigned by the system to an unlabeled volume and
is of the form `xxxyy`, where `xxx` is the data set number and
`yy` is the volume sequence number for the data set.
* If ***ser*** is absent from the message text, the volume is
unlabeled and is not being passed between job steps.
* ***text2*** values of `PVT`, `PUB`, and `STR` refer to the type of volume that was
used: private, public or storage.

**System Action**: The system marks the device as 'not READY'.

**Operator Response:** Demount the volume.

If `K` appeared, demount the volume and return it to the library.

If `D` appeared in the message text, use the volume later when a
scratch volume is requested.

If `R` appeared, retain the volume near the computer. If it is not
externally marked with its serial number, mark the 6-digit or
internally assigned number on the volume. (The internally
assigned number should appear externally on the volume in case
a subsequent step needs the volume; for the subsequent
mounting, the system will specify the volume by the internally
assigned number.) In the message, ***jjj*** is the name of the job which
needs the unit.

---

```text
IEF455D MOUNT ser ON ddd FOR jjj,sss OR REPLY 'NO'
```
**Explanation:** Message IEF233D which requested a mount of
volume ***ser*** on device ***ddd*** has been issued.

**System Action:** The task waits for the volume to be mounted or
for a reply of 'NO'. The job cannot be terminated until the
operator responds to this message or to message `IEF233D`.

**Operator Response**: Mount the volume as instructed in message
`IEF233D` or reply `NO`. If you reply `NO`, the device is
allocated; however the internal representation to the system still
indicates that volume ***ser*** is associated with device ***ddd***. Both the
volume and the device are available to the system but you might
want to take the following steps to unload the device and thus
adjust the system view of allocation:

1. Issue the `DISPLAY U` command for device ***ddd*** to see if
there is a mount pending for volume ***ser***.
2. If a mount is pending, issue the `UNLOAD` command to
device ***ddd*** to give the system the correct information.
