#!/usr/bin/perl
use warnings;
use strict;
use HTTP::Request::Common qw(POST);
use LWP::UserAgent;
use AppConfig;
use Unix::Syslog qw(:macros :subs);
our($PORT,$HOST,$TAPEDIR,$SCRATCHDIR,@prefix,@suffix,$LOG,$FACILITY);

=pod

 This script implements an automount facility for
 Hercules. In order to use this, you must define a virtual
 1403 to Hercules. This 1403 printer must be assigned to a
 FIFO pipe. This script receives its input from that FIFO pipe. 
 The address of this 1403 must be specified
 as an MVS console "unit(prt)" with ROUTCODE(3) only and with only
 the message text, not prefixes such as are prepended via the 
 $TOSCn,D= command in the old MVS 3.8j/JES2 world or the MFORM operand
 on the K S command, or CONSOLnn member of PARMLIB, in the OS/390 and
 z/OS world.
 This will direct all tape mount and dismount messages to this
 script, as well as some other messages.

 When this script sees a mount message, it will take one of two actions.

 If the mount is for a specific volser, it will:
 1) verify that the file $TAPEDIR/volser or $SCRATCHDIR/volser exists.
	$SCRATCHDIR/volser is searched just in case a "scratch" volume
	needs to be mounted. If the tape is found in $SCRATCHDIR,
	it is used "in place" and remains a scratch volume as far as
	this routine is concerned.
 2) if it does, it will issue "devinit devnum $TAPEDIR/volser"
 3) if it does not, something is wrong and no action is taken.
	Unfortuantely, there is no way for this routine to inform the
	guest OS that it did not mount the tape.

 If the mount is for a scratch tape, it will:
 1) Find a "scratch" volser in $SCRATCHDIR.
    Note that all files in $SCRATCHDIR are assumed to be scratch
    volumes regardless of their content. Of course, if they are not,
    then this logic will not produce the correct results. If one is
    running without a tape management system on the guest, 
    this could result in loss of data. A tape management system 
    should avoid this problem.

    How to maintain the scratch pool (moving volumes from $TAPEDIR to
    $SCRATCHDIR) is beyond the scope of this routine at this time. I have
    some ideas for the future.

 2) mv that file from $SCRATCHDIR to $TAPEDIR
 3) issue the command "mount devnum $TAPEDIR/volser"
 
 A scratch request is assumed when the "volser" in the mount message is
 either 'SCRTCH' or 'PRIVAT'. Any other value is considered to be the
 actual volser.
 
 Configuration variables in "tape-robot.cfg":
	TAPEDIR - the subdirectory containing all FakeTape(tm) volumes
		This is a single subdirectory. At present this routine
		does not support FakeTape(tm) volumes in multiple
		subdirectories. This is a "future direction".
	SCRATCHDIR - This subdirectory contains files which can be used
		as virtual tape volumes. It is assumed that all files in
		this subdirectory are valid FakeTape(tm) volumes, AWS
		formatted volumes or zero length files.
		Placing virtual volumes in this subdirectory is the 
		responsibility of the user or some other process.
	HERCPORT - The TCP port number for the Hercules HTTP process.
	HERCHOST - The DNS name or IP address of the host running Hercules.
	SUFFIXES - A list of possible suffixes for tape files.
	PREFIXES - A list of possible prefixes for tape files.
		Note that the volser in the mount message is first attempted
		without any prefix or suffix. This is as if the SUFFIXES and
		PREFIXES HAD specified a "null" string as the first element in
		them.
	LOG - Either YES or NO to indicate whether this routine should attempt
		to use the UNIX syslog facility to log its actions. The default,
		if not specified, is NO.
	FACILITY - Must be a valid syslog facility. The default is local0.

=cut

sub COMMAND {
	my $ua = LWP::UserAgent->new;
	$ua->agent("Mozilla/4.0 (compatable; MSIE 6.0; Windows NT 5.0)");
	my $req = POST "http://$HOST:$PORT/cgi-bin/tasks/syslog",
		[ 'command' => $_[0] ,
		  'norefresh' => '1' ,
		  'refresh_interval' => '5',
		  'msgcount' => '22' ];
	my $res = $ua->request($req);
#	print STDERR "$_[0]\n";
	syslog LOG_INFO,"%s","$_[0]";
#	print $res->as_string;
	}
sub MOUNT {
	my($devnum,$volser)=@_;
	my($volsers,$vol,@args,$scrtape,$file,$test,@volsers,$cmd);
	my($dir,$prefix,$suffix);
	if ($volser eq "PRIVAT" || $volser eq "SCRTCH") {
		opendir(HANDLE,$SCRATCHDIR);
		@volsers=readdir(HANDLE);
#		@volsers=glob("$SCRATCHDIR/*");
#		print STDERR $#volsers," scratch volumes in $SCRATCHDIR\n";
		closedir(HANDLE);
		foreach $vol (@volsers,"-") {
			$volser=$vol;
			$scrtape="$SCRATCHDIR/$vol";
#			print STDERR "testing scratch tape $scrtape\n";
			$test="$TAPEDIR/$vol";
			@args=("mv",$scrtape,$test);
			last if -f $scrtape && ! -e $test && (system(@args) == 0);
		}
	}
	if ($volser eq "-") {
#		print STDERR "Error. No scratch tapes available.\n",$_;
		syslog LOG_ERR,"%s","Error. No scratch tapes available.";
		return;
	}
	$file="$TAPEDIR/$volser";
VOL:	foreach $dir ($TAPEDIR, $SCRATCHDIR) {
		foreach $prefix (@prefix) {
			foreach $suffix (@suffix) {
				$file="$dir/$prefix$volser$suffix";
				last VOL if -f $file;
			}
		}
	}
	unless ( -f $file) {
#		print STDERR "Error. Volume $volser does not appear to exist.";
#		print STDERR "No action taken.\n";
		syslog LOG_ERR,"%s","Volume $volser does not appear to exist.";
		return;
		}
	$cmd="devinit $devnum $file";
	&COMMAND($cmd);
#	print "$cmd\n";
	return;
}
#
my($devnum,$file,$volser,$cmd,$prefix,$suffix,$facility);
my $config=AppConfig->new();
my %facilities=( 'local0' => LOG_LOCAL0,
		 'local1' => LOG_LOCAL1,
		 'local2' => LOG_LOCAL2,
		 'local3' => LOG_LOCAL3,
		 'local4' => LOG_LOCAL4,
		 'local5' => LOG_LOCAL5,
		 'local6' => LOG_LOCAL6,
		 'local7' => LOG_LOCAL7,
		 'kern'   => LOG_KERN,
		 'user'   => LOG_USER,
		 'mail'   => LOG_MAIL,
		 'daemon' => LOG_DAEMON,
		 'auth'   => LOG_AUTH,
		 'syslog' => LOG_SYSLOG,
		 'lpr'    => LOG_LPR,
		 'news'   => LOG_NEWS,
		 'uucp'   => LOG_UUCP,
		 'cron'   => LOG_CRON );
$config->define('HERCPORT=s');
$config->define('HERCHOST=s');
$config->define('SCRATCHDIR=s');
$config->define('TAPEDIR=s');
$config->define('SUFFIXES=s@');
$config->define('PREFIXES=s@');
$config->define('LOG!');
$config->define('FACILITY=s');
$config->define('DEVNUMS=s@');
$config->file('tape-robot.cfg');
$PORT=$config->get('HERCPORT') || 8080;
print STDERR "HERCPORT=$PORT\n";
$HOST=$config->get('HERCHOST') || 'localhost';
print STDERR "HERCHOST=$HOST\n";
$LOG=$config->get('LOG') || 0;
if ($LOG) {
	$FACILITY=lc $config->get('FACILITY') || 'local0';
	$facility=$facilities{$FACILITY} || '';
	if ($facility) {
		print STDERR "Logging is ON.\n";
		print STDERR "Logging is to the $FACILITY facility.\n";
		openlog 'tape-robot',LOG_PID|LOG_PERROR,$facility;
		}
	else {
		print STDERR "Specified facility:$FACILITY is invalid.\n";
		print STDERR "Logging is turned off.\n";
		$LOG=0;
	}
} else {
	print STDERR "Logging is OFF\n";
}
$TAPEDIR=$config->get('TAPEDIR') or die 'TAPEDIR not specified in configuration file.';
print STDERR "TAPEDIR is $TAPEDIR\n";
$SCRATCHDIR=$config->get('SCRATCHDIR') or die 'SCRATCHDIR not specified in configuration file.';
print STDERR "SCRATCHDIR is $SCRATCHDIR\n";
my $suffixes=$config->get('SUFFIXES');
@suffix=split " ", join ' ', @$suffixes;
unshift @suffix, '';
my $prefixes=$config->get('PREFIXES');
@prefix=split " ", join ' ',@$prefixes;
unshift @prefix, '';
my $DEVNUMS=$config->get('DEVNUMS');
my $devpat;
if (@$DEVNUMS) {
	$devpat='(?:'.(join ')|(',split ' ',join ' ',@$DEVNUMS).')';
} else {
	$devpat='(?:.*)';
}
print STDERR "Device Number pattern is $devpat\n";
#$devpat=qr/$devpat/;
die("TAPEDIR and SCRATCHDIR may not be the same directory.\n") if ($TAPEDIR eq $SCRATCHDIR);
die "TAPEDIR $TAPEDIR is not a directory.\n" unless -d $TAPEDIR;
die "TAPEDIR $TAPEDIR is not writable.\n" unless -w $TAPEDIR;
die "TAPEDIR $TAPEDIR is not readable.\n" unless -r $TAPEDIR;
die "SCRATCHDIR $SCRATCHDIR is not a directory.\n" unless -d $SCRATCHDIR;
die "SCRATCHDIR $SCRATCHDIR is not writable.\n" unless -w $SCRATCHDIR;
die "SCRATCHDIR $SCRATCHDIR is not readable.\n" unless -r $SCRATCHDIR;
#
while (<>) {
	print STDERR $_;
	if (($devnum) = /^.(?:IEC502E|IEF234E) (?:K|D|RK|RD|R) (.{3,4}),/o) {
		next unless $devnum =~ /$devpat/o;
		$cmd="devinit $devnum *";
		&COMMAND($cmd);
	}
	elsif (($volser, $devnum) = /^.IEF455D MOUNT (......) ON (.{3,4}) /o) {
		next unless $devnum =~ /$devpat/o;
		&MOUNT($devnum,$volser);
	}
	elsif (($devnum, $volser) = /^.(?:IEC501A|IEF233[AD]) M (.{3,4}),(......)/o ) {
		next unless $devnum =~ /$devpat/o;
		&MOUNT($devnum,$volser);
	}
	elsif (($devnum, $volser) = /^.EDG6627A M (....{4}) V\((......)\)/o ) {
		next unless $devnum =~ /$devpat/;
		$file="$SCRATCHDIR/$volser";
		if ( -f $file ) {
			$cmd="devinit $devnum $file";
#			print "$cmd\n";
		}
	}
}
