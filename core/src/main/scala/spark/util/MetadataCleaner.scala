package spark.util

import java.util.concurrent.{TimeUnit, ScheduledFuture, Executors}
import java.util.{TimerTask, Timer}
import spark.Logging


/**
 * Runs a timer task to periodically clean up metadata (e.g. old files or hashtable entries)
 */
class MetadataCleaner(name: String, cleanupFunc: (Long) => Unit) extends Logging {
  val delaySeconds = MetadataCleaner.getDelaySeconds
  val periodSeconds = math.max(10, delaySeconds / 10)
  val timer = new Timer(name + " cleanup timer", true)

  val task = new TimerTask {
    def run() {
      try {
        cleanupFunc(System.currentTimeMillis() - (delaySeconds * 1000))
        logInfo("Ran metadata cleaner for " + name)
      } catch {
        case e: Exception => logError("Error running cleanup task for " + name, e)
      }
    }
  }

  if (delaySeconds > 0) {
    logDebug(
      "Starting metadata cleaner for " + name + " with delay of " + delaySeconds + " seconds " +
      "and period of " + periodSeconds + " secs")
    timer.schedule(task, periodSeconds * 1000, periodSeconds * 1000)
  }

  def cancel() {
    timer.cancel()
  }
}


object MetadataCleaner {
  def getDelaySeconds = System.getProperty("spark.cleaner.delay", "-1").toInt
  def setDelaySeconds(delay: Int) { System.setProperty("spark.cleaner.delay", delay.toString) }
}

